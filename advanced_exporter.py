import paramiko
from prometheus_client import Gauge, start_http_server
import time
import argparse
import sys
import logging

# Cau hinh ghi log de ghi lai cac thong bao va su kien
logging.basicConfig(
    level=logging.INFO,  # Cap do thong tin duoc ghi (INFO)
    format='%(asctime)s - %(levelname)s - %(message)s'  # Dinh dang log
)
logger = logging.getLogger(__name__)

# Dinh nghia cac metric Prometheus
# Cac metric nay luu tru cac gia tri thu thap duoc tu router
memory_available = Gauge('router_memory_available', 'Available Memory in kB')
memory_used = Gauge('router_memory_used', 'Used Memory in kB')
memory_cached = Gauge('router_memory_cached', 'Cached Memory in kB')
uptime = Gauge('router_uptime', 'Router Uptime in Seconds')
load_avg_1m = Gauge('router_load_avg_1m', 'Router Load Average (1 minute)')
load_avg_5m = Gauge('router_load_avg_5m', 'Router Load Average (5 minutes)')
load_avg_15m = Gauge('router_load_avg_15m', 'Router Load Average (15 minutes)')
cpu_usage = Gauge('router_cpu_usage', 'CPU Usage Percentage')
network_rx_bytes = Gauge('router_network_rx_bytes', 'Received Network Bytes', ['interface'])
network_tx_bytes = Gauge('router_network_tx_bytes', 'Transmitted Network Bytes', ['interface'])
tcp_connections = Gauge('router_tcp_connections', 'Number of TCP Connections')
connected_devices = Gauge('router_connected_devices', 'Number of Connected Devices')

def fetch_router_data(router_ip, username, password):
    """Thu thap cac thong so tu router qua SSH."""
    try:
        # Ket noi SSH toi router
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(router_ip, username=username, password=password, timeout=10)

        # Lay thong tin bo nho
        stdin, stdout, stderr = client.exec_command("cat /proc/meminfo")
        mem_data = stdout.read().decode('utf-8')
        mem_total = mem_available = mem_cached = 0
        for line in mem_data.split('\n'):
            if "MemTotal" in line:
                mem_total = int(line.split()[1])
            elif "MemAvailable" in line:
                mem_available = int(line.split()[1])
            elif "Cached" in line:
                mem_cached = int(line.split()[1])
        
        # Cap nhat cac metric lien quan den bo nho
        memory_available.set(mem_available)
        memory_cached.set(mem_cached)
        memory_used.set(mem_total - mem_available)

        # Thoi gian uptime cua router
        stdin, stdout, stderr = client.exec_command("cat /proc/uptime")
        uptime_seconds = stdout.read().decode('utf-8').split()[0]
        uptime.set(float(uptime_seconds))

        # Thong so tai he thong (load average)
        stdin, stdout, stderr = client.exec_command("cat /proc/loadavg")
        loadavg_data = stdout.read().decode('utf-8').strip()
        load_1m, load_5m, load_15m, *_ = loadavg_data.split()
        load_avg_1m.set(float(load_1m))
        load_avg_5m.set(float(load_5m))
        load_avg_15m.set(float(load_15m))

        # Su dung CPU
        stdin, stdout, stderr = client.exec_command("cat /proc/stat")
        cpu_data = stdout.read().decode('utf-8').splitlines()[0]
        cpu_fields = list(map(int, cpu_data.split()[1:]))
        cpu_total_time = sum(cpu_fields)
        cpu_idle_time = cpu_fields[3]
        cpu_usage.set(100 * (1 - cpu_idle_time / cpu_total_time))

        # Su dung mang
        stdin, stdout, stderr = client.exec_command("cat /proc/net/dev")
        network_data = stdout.read().decode('utf-8').splitlines()
        for line in network_data[2:]:
            fields = line.split()
            interface = fields[0].strip(":")
            if interface in ["lo"]:  # Bo qua interface loopback
                continue

            rx_bytes = int(fields[1])  # Du lieu nhan
            tx_bytes = int(fields[9])  # Du lieu gui

            network_rx_bytes.labels(interface=interface).set(rx_bytes)
            network_tx_bytes.labels(interface=interface).set(tx_bytes)

        # So luong ket noi TCP
        stdin, stdout, stderr = client.exec_command("cat /proc/net/tcp")
        tcp_data = stdout.read().decode('utf-8').splitlines()
        tcp_connections.set(len(tcp_data) - 1)

        # So thiet bi ket noi (lay tu bang ARP)
        stdin, stdout, stderr = client.exec_command("arp -a")
        arp_data = stdout.read().decode('utf-8').splitlines()
        device_count = len(arp_data)
        connected_devices.set(device_count)

        # Log danh sach thiet bi ket noi
        logger.info("Connected devices (from ARP):")
        for device in arp_data:
            logger.info(device)

        # Dong ket noi SSH
        client.close()
        logger.info("Successfully collected metrics from router")
    except Exception as e:
        # Ghi loi neu qua trinh thu thap that bai
        logger.error(f"Error fetching data: {e}")
        raise

def main():
    """Ham chinh chay exporter."""
    parser = argparse.ArgumentParser(description='DD-WRT Router Metrics Exporter')
    parser.add_argument('--port', type=int, default=9200, help='Port de xuat metric')
    parser.add_argument('--router-ip', type=str, default='192.168.1.1', help='Dia chi IP cua router')
    parser.add_argument('--username', type=str, default='root', help='Ten nguoi dung cua router')
    parser.add_argument('--password', type=str, required=True, help='Mat khau cua router')
    parser.add_argument('--interval', type=int, default=10, help='Khoang thoi gian thu thap (giay)')
    
    args = parser.parse_args()

    try:
        # Bat dau HTTP server Prometheus
        start_http_server(args.port)
        logger.info(f"Prometheus metrics server started on port {args.port}")

        # Vong lap thu thap du lieu
        while True:
            try:
                fetch_router_data(args.router_ip, args.username, args.password)
            except Exception as e:
                logger.error(f"Error in metrics collection cycle: {e}")
            
            time.sleep(args.interval)

    except KeyboardInterrupt:
        # Ket thuc chuong trinh khi nhan Ctrl+C
        logger.info("Exporter stopped by user")
        sys.exit(0)
    except Exception as e:
        # Ghi loi va thoat neu xay ra loi nghiem trong
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

