import asyncio
from fastapi import HTTPException
from schemas import ConfigureClientData, ConfigureAccessPointData

async def run_subprocess(command: str):
    process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    exit_status = process.returncode
    if exit_status != 0:
        raise HTTPException(400, f"failed to execute command: {command}")
    return stdout, stderr

def _is_client_config_active(link_status: str, new_ssid: str) -> bool:
    if link_status.find(f"SSID: {new_ssid}") != -1:
        return True
    else:
        return False

async def is_client_config_active(request_body: ConfigureClientData) -> bool:
    if request_body.radio == "5G":
        stdout, stderr = await run_subprocess("iw dev wlan0 link")
    else:
        stdout, stderr = await run_subprocess("iw dev wlan1 link")
    return _is_client_config_active(str(stdout), request_body.ssid)
    
def _is_ap_config_active(link_status: str, ssid: str, tx_power: int, request_body: ConfigureAccessPointData) -> bool:
    if int(link_status[link_status.find("TX packets:") + 11]) > 0 and ssid == request_body.ssid and tx_power == request_body.tx_power:
        return True
    else:
        return False

async def is_ap_config_active(request_body: ConfigureAccessPointData) -> bool:
    if request_body.radio == "5G":
        link_status, _ = await run_subprocess("ifconfig wlan0")
        ssid, _ = await run_subprocess("uci get wireless.AP_radio0.ssid")
        tx_power, _ = await run_subprocess("uci get wireless.AP_radio0.txpower")
    else:
        link_status, _ = await run_subprocess("ifconfig wlan1")
        ssid, _ = await run_subprocess("uci get wireless.AP_radio1.ssid")
        tx_power, _ = await run_subprocess("uci get wireless.AP_radio1.txpower")
    return _is_ap_config_active(str(link_status), str(ssid), str(tx_power), request_body)   
            
    
    # from utils.run_subprocess import check_inuse_client_config

test_client_status = """iw dev wlan0 link
Connected to 68:7f:74:3b:b0:01 (on wlan0)
        SSID: tesla-5g-bcm
        freq: 5745
        RX: 30206 bytes (201 packets)
        TX: 4084 bytes (23 packets)
        signal: -31 dBm
        tx bitrate: 300.0 MBit/s MCS 15 40Mhz short GI"""
        
test_ap_status = """
wlan0     Link encap:Ethernet  HWaddr 00:25:9C:13:D2:3C
          inet addr:192.168.0.121  Bcast:192.168.0.255  Mask:255.255.255.0
          inet6 addr: fe80::225:9cff:fe13:d23c/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:222 errors:0 dropped:0 overruns:0 frame:0
          TX packets:132 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:42984 (41.9 KiB)  TX bytes:13259 (12.9 KiB)"""
          
# print(test_ap_status.split().find("TX packets:"))