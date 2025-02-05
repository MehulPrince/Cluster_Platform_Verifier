import subprocess
import sys
import json
import paramiko
import platform


def install_paramiko():
    """Check if paramiko is installed, and install it if not."""
    try:
        import paramiko
    except ImportError:
        print("Paramiko not found. Installing...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "paramiko"])


# Call the install function before running the rest of your script
install_paramiko()


def ping_node(ip):
    """Ping a node and return True if reachable, else False."""
    try:
        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["ping", "-n", "3", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            result = subprocess.run(
                ["ping", "-c", "3", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception as e:
        print(f"Ping error: {e}")
        return False


def get_interfaces_via_ssh(ip, username, password):
    """Retrieve network interfaces from a node via SSH."""
    interfaces = []
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        stdin, stdout, stderr = ssh.exec_command(
            "ip -o link show | awk -F': ' '{print $2}'")
        interfaces = stdout.read().decode().splitlines()

    except Exception as e:
        print(f"Error retrieving interfaces for {ip}: {e}")
    finally:
        ssh.close()
    return interfaces


def configure_interfaces(ip, username, password, interfaces, node_number):
    """Generate and configure interface IPs via SSH."""
    configurations = []
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        for index, interface in enumerate(interfaces, start=1):
            if interface == "enp1s0":
                continue  # Skip configuring enp1s0
            ip_address = f"31.31.{node_number}.{index}"
            configurations.append((interface, ip_address))

            # Bring the interface up and configure the IP
            ssh.exec_command(f"sudo ip addr add {
                             ip_address}/24 dev {interface}")
            ssh.exec_command(f"sudo ip link set {interface} up")

    except Exception as e:
        print(f"Error configuring interfaces for {ip}: {e}")
    finally:
        ssh.close()
    return configurations


def get_disk_details_via_ssh(ip, username, password):
    """Retrieve disk details from a node via SSH."""
    disk_details = ""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        # Use `lsblk` to get disk details
        stdin, stdout, stderr = ssh.exec_command(
            "lsblk -o NAME,SIZE,TYPE,MOUNTPOINT")
        disk_details = stdout.read().decode()

    except Exception as e:
        print(f"Error retrieving disk details for {ip}: {e}")
    finally:
        ssh.close()
    return disk_details


def check_pci_devices_via_ssh(ip, username, password, pci_devices):
    """Check if specified PCI devices are present on the node."""
    pci_results = {}
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        # Get the list of PCI devices using `lspci -n`
        stdin, stdout, stderr = ssh.exec_command("lspci -n")
        pci_output = stdout.read().decode().splitlines()

        # Check for each PCI device in the list
        for device in pci_devices:
            vendor_id, device_id = device.split(":")
            found = False

            for line in pci_output:
                if f"{vendor_id}:{device_id}" in line:
                    found = True
                    break

            pci_results[device] = found

    except Exception as e:
        print(f"Error checking PCI devices for {ip}: {e}")
    finally:
        ssh.close()
    return pci_results


def run_fio_test_via_ssh(ip, username, password, io_pattern="randwrite", block_size="1B", numjobs=8, size="100M", runtime=10):
    """Run fio benchmark on a node via SSH and return the results."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        # Check if fio is installed
        stdin, stdout, stderr = ssh.exec_command("which fio")
        if not stdout.read().strip():
            print(f"fio is not installed on {
                  ip}. Please install fio to run benchmarks.")
            return None

        # Use a temporary file for the FIO test
        test_file = "/tmp/fio_test_file"

        # Build the fio command dynamically based on parameters
        command = (
            f"fio --name=readwrite --ioengine=sync --rw={
                io_pattern} --bs={block_size} "
            f"--numjobs={numjobs} --size={size} --runtime={runtime} --time_based "
            f"--output-format=json --filename={test_file}"
        )

        # Execute the fio command
        stdin, stdout, stderr = ssh.exec_command(command)

        # Read the complete output of the command
        fio_output = stdout.read().decode()

        # Parse the FIO output
        try:
            fio_result = json.loads(fio_output)

            # Extract relevant results (IOPS, Throughput, Latency, CPU usage)
            job_data = fio_result['jobs'][0]
            iops = job_data['read']['iops'] + job_data['write']['iops']
            # Convert to KB/s
            throughput = (job_data['read']['bw'] +
                          job_data['write']['bw']) / 1024
            latency_avg = (job_data['read']['lat_ns']['mean'] + job_data['write']
                           # Convert to microseconds
                           ['lat_ns']['mean']) / 1000
            latency_95th = (job_data['read']['lat_ns']['percentile']['95.000000'] + job_data['write']
                            # Convert to microseconds
                            ['lat_ns']['percentile']['95.000000']) / 1000
            cpu_usage = job_data['usr_cpu'] + \
                job_data['sys_cpu']  # Total CPU usage

            fio_details = (
                f"\nFio Benchmark Results:\n"
                f"IOPS: {iops:.2f}\n"
                f"Throughput: {throughput:.2f} KB/s\n"
                f"Average Latency: {latency_avg:.2f} us\n"
                f"95th Percentile Latency: {latency_95th:.2f} us\n"
                f"CPU Usage: {cpu_usage:.2f}%\n"
            )

        except Exception as e:
            fio_details = f"Error parsing fio output: {
                e}\nRaw FIO Output:\n{fio_output}"

        # Clean up the temporary test file
        ssh.exec_command(f"rm -f {test_file}")

    except Exception as e:
        print(f"Error running fio on {ip}: {e}")
        return None
    finally:
        ssh.close()
    return fio_details


def main():
    input_file = "Config.json"
    output_file = "output.txt"

    try:
        # Load JSON data
        with open(input_file, "r") as f:
            data = json.load(f)

        nodes = data.get("nodes", [])

        if not nodes:
            print("No nodes found in the configuration.")
            return

        # Prepare the output file
        with open(output_file, "w") as f:
            f.write("Ping and Configuration Details\n")
            f.write("=" * 50 + "\n")

            for node in nodes:
                node_id = node["node_id"]
                management_ip = node["management_ip"]
                password = node["password"]
                username = node["username"]
                network_controllers = node.get("network_controllers", [])
                storage_controllers = node.get("storage_controllers", [])

                # Ping the node
                is_reachable = ping_node(management_ip)

                f.write(f"Node: {node_id}, Management IP: {management_ip}\n")
                f.write(f"Ping Status: {
                        'Reachable' if is_reachable else 'Unreachable'}\n")

                if is_reachable:
                    # Retrieve and configure interfaces
                    interfaces = get_interfaces_via_ssh(
                        management_ip, username, password)
                    node_number = int(node_id.lstrip("node"))
                    configurations = configure_interfaces(
                        management_ip, username, password, interfaces, node_number)

                    f.write("Interfaces (with configured IPs):\n")
                    for interface_name, ip in configurations:
                        f.write(f"  {interface_name}: {ip} (Configured Up)\n")

                    # Retrieve disk details
                    disk_details = get_disk_details_via_ssh(
                        management_ip, username, password)
                    f.write("\nDisk Details:\n")
                    f.write(disk_details)

                    # Check network controllers
                    if network_controllers:
                        network_results = check_pci_devices_via_ssh(
                            management_ip, username, password, network_controllers)
                        f.write("\nNetwork Controllers Check:\n")
                        for device, found in network_results.items():
                            f.write(f"  {device}: {
                                    'Found' if found else 'Not Found'}\n")

                    # Check storage controllers
                    if storage_controllers:
                        storage_results = check_pci_devices_via_ssh(
                            management_ip, username, password, storage_controllers)
                        f.write("\nStorage Controllers Check:\n")
                        for device, found in storage_results.items():
                            f.write(f"  {device}: {
                                    'Found' if found else 'Not Found'}\n")

                    # Run fio benchmark
                    fio_result = run_fio_test_via_ssh(
                        management_ip, username, password)
                    if fio_result:
                        f.write(fio_result)
                else:
                    f.write(
                        "Interfaces: Node not reachable, no configurations applied.\n")
                f.write("-" * 50 + "\n")

        print(f"Details written to {output_file}")

    except FileNotFoundError:
        print(f"Error: The file {input_file} was not found.")
    except json.JSONDecodeError:
        print(f"Error: The file {input_file} contains invalid JSON.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
