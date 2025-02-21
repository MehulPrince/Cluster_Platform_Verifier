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
            ssh.exec_command(f"sudo ip addr add {ip_address}/24 dev {interface}")
            ssh.exec_command(f"sudo ip link set {interface} up")

    except Exception as e:
        print(f"Error configuring interfaces for {ip}: {e}")
    finally:
        ssh.close()
    return configurations


def get_disk_details_via_ssh(ip, username, password):
    """Retrieve disk details from a node via SSH and return a list of disks."""
    disks = []
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        # Use `lsblk` to get disk details (only disks, not partitions)
        stdin, stdout, stderr = ssh.exec_command("lsblk -d -o NAME,TYPE | grep disk | awk '{print $1}'")
        disks = stdout.read().decode().splitlines()

        # Verify that the disks exist
        for disk in disks:
            stdin, stdout, stderr = ssh.exec_command(f"test -e /dev/{disk} && echo 'exists' || echo 'missing'")
            if "exists" not in stdout.read().decode():
                print(f"Disk {disk} does not exist on {ip}.")
                disks.remove(disk)

    except Exception as e:
        print(f"Error retrieving disk details for {ip}: {e}")
    finally:
        ssh.close()
    return disks


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


def run_fio_test_via_ssh(ip, username, password, disk, io_pattern="randrw", block_size="4k", numjobs=8, size="100M", runtime=60):
    """Run fio benchmark on a specific disk via SSH and return the parsed results."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        # Check if fio is installed
        stdin, stdout, stderr = ssh.exec_command("which fio")
        fio_path = stdout.read().decode().strip()
        if not fio_path:
            print(f"fio is not installed on {ip}. Please install fio to run benchmarks.")
            return None
        print(f"fio found at: {fio_path}")

        # Use the specified disk for the FIO test
        test_file = f"/dev/{disk}"

        # Build the fio command dynamically based on parameters
        command = (
            f"sudo fio --name=readwrite --ioengine=sync --rw={io_pattern} --bs={block_size} "
            f"--numjobs={numjobs} --size={size} --runtime={runtime} --time_based "
            f"--output-format=json --filename={test_file}"
        )

        print(f"Running FIO command: {command}")

        # Execute the fio command
        stdin, stdout, stderr = ssh.exec_command(command)
        
        # Read the complete output of the command
        fio_output = stdout.read().decode()
        fio_error = stderr.read().decode()

        print(f"FIO Output: {fio_output}")
        print(f"FIO Error: {fio_error}")

        # Parse the FIO output
        try:
            fio_result = json.loads(fio_output)
            
            # Extract relevant results (IOPS, Throughput, Latency, CPU usage)
            job_data = fio_result['jobs'][0]
            read_iops = job_data['read']['iops']
            write_iops = job_data['write']['iops']
            read_latency = job_data['read']['lat_ns']['mean'] / 1000  # Convert to microseconds
            write_latency = job_data['write']['lat_ns']['mean'] / 1000  # Convert to microseconds
            cpu_usage = job_data['usr_cpu'] + job_data['sys_cpu']  # Total CPU usage

            # Prepare parsed FIO data
            fio_details = {
                "disk": disk,
                "read_iops": read_iops,
                "write_iops": write_iops,
                "read_latency_us": read_latency,
                "write_latency_us": write_latency,
                "cpu_usage_percent": cpu_usage
            }

        except Exception as e:
            fio_details = f"Error parsing fio output for disk {disk}: {e}\nRaw FIO Output:\n{fio_output}"

    except Exception as e:
        print(f"Error running fio on {ip} for disk {disk}: {e}")
        return None
    finally:
        ssh.close()
    return fio_details


def run_iperf_test(server_ip, server_username, server_password, client_ips, client_username, client_password):
    """
    Run iperf test between a server and multiple clients.
    Returns a dictionary with bandwidth results for each client.
    """
    results = {}
    try:
        # Start iperf server on the server node
        server_ssh = paramiko.SSHClient()
        server_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        server_ssh.connect(server_ip, username=server_username, password=server_password)

        # Start iperf server in the background
        server_ssh.exec_command("iperf -s &")
        print(f"Started iperf server on {server_ip}")

        # Wait for the server to start
        import time
        time.sleep(2)

        # Run iperf clients on each client node
        for client_ip in client_ips:
            try:
                client_ssh = paramiko.SSHClient()
                client_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client_ssh.connect(client_ip, username=client_username, password=client_password)

                # Run iperf client command
                stdin, stdout, stderr = client_ssh.exec_command(f"iperf -c {server_ip} -t 10")
                iperf_output = stdout.read().decode()

                # Parse the iperf output to extract bandwidth
                bandwidth = None
                for line in iperf_output.splitlines():
                    if "Gbits/sec" in line or "Mbits/sec" in line:
                        bandwidth = line.strip()
                        break

                results[client_ip] = bandwidth if bandwidth else "Failed to measure bandwidth"

            except Exception as e:
                results[client_ip] = f"Error running iperf on {client_ip}: {e}"
            finally:
                client_ssh.close()

    except Exception as e:
        print(f"Error starting iperf server on {server_ip}: {e}")
    finally:
        # Stop the iperf server
        server_ssh.exec_command("pkill iperf")
        server_ssh.close()

    return results


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

            # Collect all configured IPs and their node details
            all_configured_ips = {}
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
                f.write(f"Ping Status: {'Reachable' if is_reachable else 'Unreachable'}\n")

                if is_reachable:
                    # Retrieve and configure interfaces
                    interfaces = get_interfaces_via_ssh(management_ip, username, password)
                    node_number = int(node_id.lstrip("node"))
                    configurations = configure_interfaces(management_ip, username, password, interfaces, node_number)

                    f.write("Interfaces (with configured IPs):\n")
                    for interface_name, ip in configurations:
                        f.write(f"  {interface_name}: {ip} (Configured Up)\n")

                    # Retrieve disk details
                    disks = get_disk_details_via_ssh(management_ip, username, password)
                    f.write("\nDisk Details:\n")
                    for disk in disks:
                        f.write(f"  {disk}\n")

                    # Run FIO benchmarks for each disk
                    f.write("\nFIO Benchmark Results:\n")
                    for disk in disks:
                        fio_result = run_fio_test_via_ssh(management_ip, username, password, disk)
                        if fio_result and isinstance(fio_result, dict):
                            f.write(f"  Disk: {fio_result['disk']}\n")
                            f.write(f"    Read IOPS: {fio_result['read_iops']:.2f}\n")
                            f.write(f"    Write IOPS: {fio_result['write_iops']:.2f}\n")
                            f.write(f"    Read Latency: {fio_result['read_latency_us']:.2f} us\n")
                            f.write(f"    Write Latency: {fio_result['write_latency_us']:.2f} us\n")
                            f.write(f"    CPU Usage: {fio_result['cpu_usage_percent']:.2f}%\n")
                        else:
                            f.write(f"  Error running FIO on disk {disk}\n")

                    # Check network controllers
                    if network_controllers:
                        network_results = check_pci_devices_via_ssh(management_ip, username, password, network_controllers)
                        f.write("\nNetwork Controllers Check:\n")
                        for device, found in network_results.items():
                            f.write(f"  {device}: {'Found' if found else 'Not Found'}\n")

                    # Check storage controllers
                    if storage_controllers:
                        storage_results = check_pci_devices_via_ssh(management_ip, username, password, storage_controllers)
                        f.write("\nStorage Controllers Check:\n")
                        for device, found in storage_results.items():
                            f.write(f"  {device}: {'Found' if found else 'Not Found'}\n")
                else:
                    f.write("Interfaces: Node not reachable, no configurations applied.\n")
                f.write("-" * 50 + "\n")

        print(f"Details written to {output_file}")

    except FileNotFoundError:
        print(f"Error: The configuration file '{input_file}' was not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to parse the JSON configuration file '{input_file}'.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
