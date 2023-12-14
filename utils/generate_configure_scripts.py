from fastapi import HTTPException
from schemas import ConfigureClientData, ConfigureAccessPointData, SimulateScenarioData, SimulateDetail

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
    
def _generate_script_for_run_client_simulation(scenario: SimulateDetail):
    if scenario.simulation_type == "deterministic":
        return f"python -u ./simulation/client/deterministic.py {scenario.timeout} {scenario.average_packet_size} {scenario.average_interval_time}"

def _generate_script_for_run_ap_simulation(scenario: SimulateDetail):
    if scenario.simulation_type == "deterministic":
        return f"python -u ./simulation/server/deterministic.py {scenario.timeout}"

def generate_scripts_for_run_simulation(request_body: SimulateScenarioData):
    scripts = []
    if request_body.simulation_mode == "client":
        for scenario in request_body.simulation_scenarios:
            scripts.append(
                _generate_script_for_run_client_simulation(scenario))
    else:
        for scenario in request_body.simulation_scenarios:
            scripts.append(
                _generate_script_for_run_ap_simulation(scenario))
    return scripts