from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional

class OperationModeEnum(str, Enum):
    client = "client"
    AP = "AP"

class RadioEnum(str, Enum):
    radio0 = "5G"
    radio1 = "2.4G"

class ConfigureClientData(BaseModel):

    radio: RadioEnum
    connect_to_target_ap: bool
    ssid: str
    password: Optional[str] = None
    
class ConfigureAccessPointData(BaseModel):

    radio: RadioEnum
    ssid: str
    tx_power: Optional[int] = 20
    
# password already be preconfigure in case it is ap_mode or client_mode that not connect to target ap
# else: need the password

class SimulateTypeEnum(str, Enum):
    deterministic = "deterministic"
    web_application = "web_application"
    file_transfer = "file_transfer"


class SimulateDetail(BaseModel):

    simulation_type: SimulateTypeEnum
    timeout: int
    average_interval_time: Optional[int] = None
    average_packet_size: Optional[int] = None
    # average_new_page_packet_size: Optional[int] = None
    # probability_of_load_new_page: Optional[int] = None


class SimulateModeEnum(str, Enum):
    server = "server"
    client = "client"


class SimulateScenarioData(BaseModel):

    alias_name: str
    simulation_mode: SimulateModeEnum
    server_ip: Optional[str] = None
    simulation_scenarios: list[SimulateDetail]

    def my_validator(self) -> 'SimulateScenarioData':
        if self.simulation_mode == "client":
            if not self.server_ip:
                self.server_ip = "192.168.2.1"
            for scenario in self.simulation_scenarios:
                if scenario.simulation_type == "web_application":
                    # all parameter is required
                    if scenario.average_interval_time is None or scenario.average_packet_size is None:
                        raise ValueError(
                            "type web_appliacation required all parameters")
                elif scenario.simulation_type == "deterministic":
                    if scenario.average_interval_time is None or scenario.average_packet_size is None:
                        raise ValueError(
                            "type web_appliacation required average_packet_size and average_interval_time")
                elif scenario.simulation_type == "file_transfer":
                    if scenario.average_packet_size is None:
                        raise ValueError(
                            "type web_appliacation required average_packet_size")
        # ถ้า self.simulation_mode == "server": ไม่ต้องเช็คมีหรือไม่มีก็ได้เพราะใช้แค่ simulate_type ซึ่ง required อยู่แล้ว
        return self
