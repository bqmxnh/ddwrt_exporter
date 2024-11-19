# DD-WRT Router Metrics Exporter

A Python-based Prometheus exporter to monitor and collect metrics from a DD-WRT router via SSH. The exporter gathers various system and network statistics, such as memory usage, CPU usage, network activity, and connected devices.

## Features

- Memory metrics:
  - Available memory
  - Used memory
  - Cached memory
- CPU metrics:
  - CPU usage percentage
- Network metrics:
  - Received network bytes per interface
  - Transmitted network bytes per interface
- Load average:
  - 1-minute load average
  - 5-minute load average
  - 15-minute load average
- System uptime
- Number of active TCP connections
- Number of connected devices (from ARP table)

## Requirements
- Python 3.7 or higher
- Libraries:
  - `paramiko`
  - `prometheus_client`
- A DD-WRT router accessible via SSH



