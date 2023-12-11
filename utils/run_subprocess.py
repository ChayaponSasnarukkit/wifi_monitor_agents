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
    return _is_client_config_active(stdout, request_body.ssid)
    
    
            
    
    # from utils.run_subprocess import check_inuse_client_config

test_status = """iw dev wlan0 link
Connected to 68:7f:74:3b:b0:01 (on wlan0)
        SSID: tesla-5g-bcm
        freq: 5745
        RX: 30206 bytes (201 packets)
        TX: 4084 bytes (23 packets)
        signal: -31 dBm
        tx bitrate: 300.0 MBit/s MCS 15 40Mhz short GI"""