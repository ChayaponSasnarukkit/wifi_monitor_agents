from fastapi import HTTPException
from schemas import ConfigureClientData, ConfigureAccessPointData, SimulateScenarioData, SimulateDetail
import time, subprocess

client_template = """
uci set wireless.client_{radio_name}.ssid='{ssid}'
uci set wireless.client_{radio_name}.disabled='0'
uci set wireless.{radio_name}.disabled='0'
uci commit
wifi
"""

client_to_target_ap_template = """
uci set wireless.client_{radio_name}.ssid='{ssid}'
uci set wireless.client_{radio_name}.key='{password}'
uci set wireless.client_{radio_name}.disabled='0'
uci set wireless.{radio_name}.disabled='0'
uci commit
wifi
"""

ap_template = """
uci set wireless.AP_{radio_name}.ssid='{ssid}'
uci set wireless.{radio_name}.txpower='{tx_power}'
uci set wireless.AP_{radio_name}.disabled='0'
uci set wireless.{radio_name}.disabled='0'
uci commit
wifi
"""

def get_radio_name(radio: str):
    if radio == "2.4G":
        return "radio1"
    elif radio == "5G":
        return "radio0"

def generate_client_script(request_body: ConfigureClientData):
    if request_body.connect_to_target_ap:
        if not request_body.password:
            raise HTTPException(400, {"message": "connect to the target_ap require password"})
        return client_to_target_ap_template.format(
                radio_name=get_radio_name(request_body.radio),
                ssid = request_body.ssid,
                password = request_body.password
            ).strip().replace("\n",";")
    else:
        return client_template.format(
                radio_name=get_radio_name(request_body.radio),
                ssid = request_body.ssid,
            ).strip().replace("\n",";")

def generate_ap_script(request_body: ConfigureAccessPointData):
    return ap_template.format(
        radio_name=get_radio_name(request_body.radio),
        ssid = request_body.ssid,
        tx_power = request_body.tx_power
    ).strip().replace("\n",";")
    
def _generate_script_for_run_client_simulation(alias_name: str, scenario: SimulateDetail, server_ip: str):
    if scenario.simulation_type == "deterministic":
        control_ip = subprocess.run(["uci", "get", "network.lan.ipaddr"], capture_output=True, text=True).stdout
        tmp_file = f"udp_client_{str(time.time()).replace('.', '_')}.json"
        return f"python -u ./simulation/client/udp_window_deterministic.py {alias_name} {scenario.timeout} {scenario.average_packet_size} {scenario.average_interval_time} {tmp_file} {control_ip} {server_ip}", tmp_file
    if scenario.simulation_type == "web_application":
        tmp_file = f"web_client_{str(time.time()).replace('.', '_')}.json"
        return f"python -u ./simulation/client/web_application.py {alias_name} {scenario.timeout} {scenario.average_packet_size} {scenario.average_interval_time} {tmp_file} {server_ip}", tmp_file
    if scenario.simulation_type == "file_transfer":
        tmp_file = f"file_client_{str(time.time()).replace('.', '_')}.json"
        return f"python -u ./simulation/client/file_transfer.py {alias_name} {scenario.timeout} {scenario.average_packet_size} {tmp_file} {server_ip}", tmp_file
    return None, None
def _generate_script_for_run_ap_simulation(alias_name: str, scenario: SimulateDetail):
    if scenario.simulation_type == "deterministic":
        tmp_file = f"udp_server_{str(time.time()).replace('.', '_')}.json"
        return f"python -u ./simulation/server/udp_window_deterministic.py {alias_name} {scenario.timeout} {tmp_file}"
    return None, None

def generate_scripts_for_run_simulation(request_body: SimulateScenarioData):
    scripts = []; tmp_files = []
    if request_body.simulation_mode == "client":
        for scenario in request_body.simulation_scenarios:
            script, file_name = _generate_script_for_run_client_simulation(request_body.alias_name, scenario, server_ip=request_body.server_ip)
            if script:
                scripts.append(script)
            if file_name:
                 tmp_files.append(file_name)
    else:
        for scenario in request_body.simulation_scenarios:
            script, file_name = _generate_script_for_run_ap_simulation(request_body.alias_name, scenario)
            if script:
                scripts.append(script)
            if file_name:
                tmp_files.append(file_name)
    return scripts, tmp_files