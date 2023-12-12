import asyncio
import signal
from asyncio.streams import StreamReader, StreamWriter
from typing import Coroutine
asyncio.windows_events

main_coroutine: Coroutine = None

def handle_sigterm(*args):
    print("SIGINT recieved")
    for task in asyncio.all_tasks():
        if task.get_coro() is main_coroutine and not task.cancelled():
            task.cancel()

async def handle_client(reader: StreamReader, writer: StreamWriter):
    try:
        print("client connected")
        # initial parameter
        # average_interval_time:00000 average_packet_size:0000000\n
        parameters = (await reader.readline()).decode('utf8').strip().split()

        # parsing the parameter
        average_interval_time = float(parameters[0][22:])/1000
        average_packet_size = int(parameters[1][20:])
        print(f"parametes: {average_interval_time} {average_packet_size}")
        
        # start simulation
        # start simulation
        while True:
            await asyncio.sleep(average_interval_time)
            data = "a"*(average_packet_size-1) + '\n'
            
            # writing data
            writer.write(data.encode('utf8'))
            await writer.drain()
            
            # read from read buffer prevent it from begin full
            try:
                # wait for 0.1 msec (average_interval_time is in msec)
                request = (await asyncio.wait_for(reader.read(1024), timeout=0.001))
                # check for eof
                if not request:
                    print("client has finished writing")
                    break
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        print("task get cancelled")
    except Exception as e:
        print(f"unexpected exception was raised when simulating: {str(e)}")
    finally:
        try:
            print("writing eof")
            writer.write_eof()
            await writer.drain()
            # if client has finished writing then closed socket
            print("closing the socket")
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), 10)
            print("completely close")
        except asyncio.TimeoutError:
            print("(writer.wait_closed() timeout: maybe the client is dead")
        except Exception as e:
            print(f"unexpected exception was raised when trying to close gracefully: {str(e)}")

async def run_server():
    server = await asyncio.start_server(handle_client, '0.0.0.0', 8888)
    print("server start at 0.0.0.0:8888")
    # Register a signal handler for SIGINT
    signal.signal(signal.SIGINT, handle_sigterm)
    try:
        await asyncio.sleep(30)  # Wait for 5 minutes (300 seconds)
    except asyncio.CancelledError:
        pass
    finally:
        print("Closing server socket.")
        server.close()
        await server.wait_closed()
        print("Cancel all pending tasks(handle_client tasks) for exit.")
        tasks = [task for task in asyncio.all_tasks() if task is not
                asyncio.current_task()]
        list(map(lambda task: task.cancel(), tasks))
        print(f"Wait for all tasks to terminate: {[task.get_coro() for task in tasks]}")
        # await asyncio.gather(*tasks) # this will raise asyncio.exceptions.CancelledError if all tasks is cancelled
        await asyncio.gather(*tasks, return_exceptions=True)
        print("All coroutines completed. Exiting.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_coroutine = run_server()
    # signal.signal(signal.SIGTERM, handle_sigterm)
    try:
        # extract argument here (timeout)
        # main_coroutine = run_server()
        # asyncio.run(main_coroutine)
        # print("finish running")
        print("hello change from term to INT")
        loop.run_until_complete(main_coroutine)
    except KeyboardInterrupt:
        print("INT INT INT INT \n\n\n")
    except Exception as e:
        print(e)
    finally:
        loop.close()
        print("\n\nexited\n\n")

# server_process = subprocess.Popen(["c:\\Users\\hp\\AppData\\Local\\Programs\\Python\\Python310\\python.exe",  "-u",
#                                            "C:\\Users\\hp\\OneDrive\\Desktop\\final_project\\wifi_monitor_agents\\simulation\\server\\deterministic.py"],
#                                           shell=False,
#                                           stdin=subprocess.PIPE,
#                                           stdout=subprocess.PIPE,
#                                           stderr=subprocess.PIPE,
#                                           )

# server_process.terminate()
# stdout, stderr = server_process.communicate()
# server_process.returncode