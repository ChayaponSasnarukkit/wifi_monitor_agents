import asyncio
import signal
from asyncio.streams import StreamReader, StreamWriter
from typing import Coroutine

main_coroutine: Coroutine = None

def handle_sigterm(*args):
    print("SIGINT recieved")
    for task in asyncio.all_tasks():
        if task.get_coro() is main_coroutine and not task.cancelled():
            task.cancel()

async def simulate_client(reader: StreamReader, writer: StreamWriter):
    try:
        # initial parameter
        # average_interval_time:00000 average_packet_size:0000000\n
        average_interval_time = 1000/1000
        average_packet_size = 100
        writer.write("average_interval_time:01000 average_packet_size:0000100\n".encode())
        
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
                    print("server has finished writing")
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

async def main():
    # create connection
    reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
    # schedule simulate_client task
    simulate_client_task = asyncio.create_task(simulate_client(reader, writer))
    # Register a signal handler for SIGINT
    signal.signal(signal.SIGINT, handle_sigterm)
    try:
        await asyncio.sleep(30) # wait for 300 sec
    except asyncio.CancelledError:
        pass
    finally:
        print("timeout terminate the simulate_client task")
        simulate_client_task.cancel()
        await simulate_client_task
        
        
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_coroutine = main()
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
