import random, sys, requests, time

server_ip = "192.168.2.1"
base_url = f"http://{server_ip}:8088"
timeout = 60
average_packet_size = 1000 # 1 kB
# average time between click in second
average_interval_time = 2000/1000 # average 2 second between click
template_log = "{} {} web_application: {}"
total_requests = 0
total_bytes = 0

def main():
    try:
        global total_bytes; global total_requests
        global base_url; global alias_name; global average_packet_size; global average_interval_time; global timeout
        check_point = time.time() + 30
        end_time = time.time() + timeout
        lambda_size = 1/average_packet_size
        lambda_time = 1/average_interval_time
        print(template_log.format(alias_name, time.time(), f"process has started"))
        while time.time() < end_time:
            try:
                # random packet size
                packet_size = int(random.expovariate(lambda_size))
                # sent request for string that have size equal to packet size
                res = requests.get(f"{base_url}/sim_api/{packet_size}")
                total_requests += 1; total_bytes += len(res.content)
                if time.time() >= check_point:
                    print(template_log.format(alias_name, time.time(), f"{total_requests} requests sent, {total_bytes} bytes recv from {base_url}"))
                    check_point += 30
                # sleep => simulate the user read the page
                time.sleep(random.expovariate(lambda_time))
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print((template_log.format(alias_name, time.time(), f"Exception {str(e)} occured from {base_url}")))
    except KeyboardInterrupt:
        pass
    finally:
        print(template_log.format(alias_name, time.time(), f"program EXIT with {total_requests} requests sent, {total_bytes} bytes recv from {base_url}"))    

if __name__ == "__main__":
    try:
        alias_name, timeout, average_packet_size, average_interval_time = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])/1000
        if len(sys.argv) == 6:
            server_ip = sys.argv[5]
            base_url = f"http://{server_ip}:8088"
    except:
        pass
    main()
    
    # python .\simulation\client\web_application.py a 60 1024 2000 127.0.0.1