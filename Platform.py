import subprocess
import sys
import json
import paramiko


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
        result = subprocess.run(["ping", "-c", "3", ip],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception as e:
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

        ssh.close()
    except Exception as e:
        print(f"Error retrieving interfaces for {ip}: {e}")
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

        ssh.close()
    except Exception as e:
        print(f"Error configuring interfaces for {ip}: {e}")
    return configurations


def get_username_via_ssh(ip, password):
    """Dynamically retrieve the username from the node via SSH."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username="root", password=password)

        stdin, stdout, stderr = ssh.exec_command("whoami")
        username = stdout.read().decode().strip()

        ssh.close()
        return username
    except Exception as e:
        print(f"Error retrieving username for {ip}: {e}")
        return "root"  # Fallback to root if username cannot be determined


def run_fio_test_via_ssh(ip, username, password, io_pattern="randwrite", block_size="1B", numjobs=8, size="100M", runtime=10):
    """Run fio benchmark on a node via SSH and return the results."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)

        # Build the fio command dynamically based on parameters
        command = f"fio --name=readwrite --ioengine=sync --rw={io_pattern} --bs={block_size} --numjobs={
            numjobs} --size={size} --runtime={runtime} --time_based --output-format=json"

        # Execute the fio command
        stdin, stdout, stderr = ssh.exec_command(command)

        # Read the complete output of the command, including both stdout and stderr
        fio_output = stdout.read().decode() + "\n" + stderr.read().decode()

        # Fio produces a JSON output, so let's parse it and extract relevant details
        try:
            fio_result = json.loads(fio_output)

            # Extract relevant results (IOPS, Throughput, Latency, CPU usage)
            job_data = fio_result['jobs'][0]
            iops = job_data['io_ops']
            # Convert from bytes to KB (for better readability)
            throughput = job_data['bw'] / 1024
            # Average latency in microseconds
            latency_avg = job_data['latency']['mean']
            # 95th percentile latency
            latency_95th = job_data['latency']['percentile']['95.000000']
            cpu_usage = job_data['cpu_util']  # CPU usage as a percentage

            fio_details = (
                f"\nFio Benchmark Results:\n"
                f"IOPS: {iops}\n"
                f"Throughput: {throughput:.2f} KB/s\n"
                f"Average Latency: {latency_avg:.2f} us\n"
                f"95th Percentile Latency: {latency_95th:.2f} us\n"
                f"CPU Usage: {cpu_usage}%\n"
            )

        except Exception as e:
            fio_details = f"Error parsing fio output: {e}"

        # Optionally, delete the test file after the fio test to save space
        ssh.exec_command("rm -f /path/to/testfile")

        ssh.close()
        return fio_details
    except Exception as e:
        print(f"Error running fio on {ip}: {e}")
        return None


def main():
    input_file = "Config.json"
    output_file = "output.txt"

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

    with open(output_file, "a") as f:  # Keep the file open for appending
        for node in nodes:
            node_id = node["node_id"]
            management_ip = node["management_ip"]
            password = node["password"]
            username = node["username"]  # Retrieve username directly from JSON

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


if __name__ == "__main__":
    main()
