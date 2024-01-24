import asyncio
import os, platform, time, json, subprocess
import signal
from fastapi import HTTPException, Request
from schemas import ConfigureClientData, ConfigureAccessPointData, SimulateScenarioData
from utils.generate_configure_scripts import generate_scripts_for_run_simulation

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
        stdout, stderr = await run_subprocess("ifconfig")
        if stdout.decode().find("wlan0") == -1:
            return False
        stdout, stderr = await run_subprocess("iw dev wlan0 link")
    else:
        stdout, stderr = await run_subprocess("ifconfig")
        if stdout.decode().find("wlan1") == -1:
            return False
        stdout, stderr = await run_subprocess("iw dev wlan1 link")
    return _is_client_config_active(stdout.decode(), request_body.ssid)
    
def _is_ap_config_active(link_status: str, ssid: str, tx_power: int, request_body: ConfigureAccessPointData) -> bool:
    if int(link_status[link_status.find("TX packets:") + 11]) > 0 and ssid == request_body.ssid and tx_power == request_body.tx_power:
        return True
    else:
        return False

async def is_ap_config_active(request_body: ConfigureAccessPointData) -> bool:
    if request_body.radio == "5G":
        stdout, stderr = await run_subprocess("ifconfig")
        if stdout.decode().find("wlan0") == -1:
            return False
        link_status, _ = await run_subprocess("ifconfig wlan0")
        ssid, _ = await run_subprocess("uci get wireless.AP_radio0.ssid")
        tx_power, _ = await run_subprocess("uci get wireless.radio0.txpower")
    else:
        stdout, stderr = await run_subprocess("ifconfig")
        if stdout.decode().find("wlan1") == -1:
            return False
        link_status, _ = await run_subprocess("ifconfig wlan1")
        ssid, _ = await run_subprocess("uci get wireless.AP_radio1.ssid")
        tx_power, _ = await run_subprocess("uci get wireless.radio1.txpower")
    return _is_ap_config_active(link_status.decode(), ssid.strip().decode(), int(tx_power.strip().decode()), request_body)   

#     app.simulate_task: asyncio.Task = None
    # app.simulate_status = ""
    # app.monitor_data = ""
    # app.writing_configure_lock = asyncio.Lock()
    # app.active_radio = None
def parsing_monitor_data(output: str):
    output = output.split("\n")
    Tx_Power = output[4].split(" ")[11]
    Signal = output[5].split(" ")[11]
    Noise = output[5].split(" ")[15]
    BitRate = output[6].split(" ")[12]
    return {"Tx-Power": Tx_Power, "Signal": Signal, "Noise": Noise, "BitRate": BitRate}

async def monitor(request: Request):
    # find the interface to monitor on
    if request.app.active_radio == "2.4G":
        interface = "wlan1"
    else:
        interface = "wlan0"
    
    while True:
        stdout, stderr = await run_subprocess(f"iwinfo {interface} info")
        now = time.time()
        data = parsing_monitor_data(stdout.decode())
        for field in request.app.monitor_data:
            request.app.monitor_data[field].append((now, data[field]))
        await asyncio.sleep(1)
    # NO CLEAN UP NEED => raise CancelledError as soon as it recieved
    
def read_json_file_and_delete_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        os.remove(file_path)
        return data
    except FileNotFoundError:
        print(f"The file {file_path} does not exist.")
    except json.JSONDecodeError:
        print(f"Error decoding JSON in {file_path}. Please check the file format.")

async def run_simulation_processes(request_body: SimulateScenarioData, request: Request):
    # TODO: buffered before send to app (send until last \n)
    running_processes = []
    finished_process = []
    try:
        # generate run_scripts
        run_scripts, transfer_files = generate_scripts_for_run_simulation(request_body)
        max_timeout = 0
        for scenario in request_body.simulation_scenarios:
            max_timeout = max(scenario.timeout, max_timeout)
        # create monitor task
        monitor_task = asyncio.create_task(monitor(request))
        # create subprocesses to run all scripts
        for script in run_scripts:
            process = await asyncio.create_subprocess_shell(script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            running_processes.append(process)
        # polling until it complete
        end_time = time.time() + max_timeout
        while True:
            # update simulate status
            for process in running_processes:
                try:
                    if process not in finished_process:
                        stdout = await asyncio.wait_for(process.stdout.read(1024), timeout=1)
                        if not stdout:
                            finished_process.append(process)
                            # process is finish writing
                            continue
                        request.app.simulate_status += stdout.decode()
                except asyncio.TimeoutError:
                    pass
            if len(finished_process) == len(running_processes) and time.time() > end_time:
                break
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        # send SIGINT to all processes that still running
        # print("inner: recived cancel")
        for process in running_processes:
            # asyncio on WINDOWS support only SIGTERM
            # process.send_signal(signal.SIGINT)
            if platform.system() == "Windows":
                # print("sending the terminate")
                process.terminate()
            else:
                print("sending signal")
                # process.send_signal(signal.SIGINT)
                # process.terminate()
                # os.kill(process.pid, signal.SIGINT)
                print(process.pid)
                result = subprocess.run(["kill", "-9", str(process.pid)], stdout=subprocess.PIPE)
                print(result.stdout.decode())
                print("?????")
        # raise 
        raise
    except Exception as e:
        request.app.simulate_status += f"{request_body.alias_name} {time.time()}: unexpected exception occur {str(e)}"
    finally:
        # TODO: make stdout of cancelled process update to app.simulate_status
        # cancel the monitor task
        monitor_task.cancel()
        # wait all process to finish
        for process in running_processes:
            print("wait process")
            stdout, stderr = await process.communicate()
            print(stdout, stderr)
            request.app.simulate_status += stdout.decode()
        # make sure monitor is finish cleaning
        await asyncio.gather(monitor_task, return_exceptions=True)
        print("read file")
        for file_path in transfer_files:
            data = read_json_file_and_delete_file(file_path)
            if data:
                request.app.monitor_data.update(data)
        # reset the app.simulate_task to None
        request.app.simulate_task: asyncio.Task = None
    
    # from utils.run_subprocess import check_inuse_client_config
async def polling_ap_state(request: Request, request_body):
    # wait for TX packet be reset (take around 10 sec)
    await asyncio.sleep(10)
    # polling check if wifi is connected with timeout 150 sec
    cnt = 0
    while cnt < 30:
        if await is_ap_config_active(request_body):
            request.app.active_radio = request_body.radio
            request.app.ap_state = "ready_to_use"
            return
        await asyncio.sleep(5)
        cnt += 1
    request.app.ap_state = "not_ready_to_use [timeout (AP is not sending ssid broadcast)]"

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