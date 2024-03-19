import sys
import socket
import math
import hashlib
from enum import Enum

MsgType = Enum('MsgType',[
    'SendReq','SendAccept','FilePkt','FilePktAck','EOFPkt'])
ProgState = Enum('ProgState',[
    # Recv mode states
    'AwaitingSendReq','SendingSendAccept','AwaitingFilePkt',
    'SendingFilePktAck',
    # Send mode states
    'SendingSendReq','AwaitingSendAccept','SendingFilePkt',
    'AwaitingFilePktAck'
])

magic_number = 0x1a # Every msg must start with this byte
sock_timeout = 20   # Seconds before socket times out.

# Takes in a byte array, divides it up into chunks of chunk_size and
# returns chunk_list containing those chunks.
def slice_data(data, chunk_size):
    chunk_count = math.ceil(len(data)/chunk_size)
    chunk_list = []
    print(f'File Data Size: {len(data)}, Chunk Count:{chunk_count}')
    for i in range(chunk_count):
        start = i*chunk_size
        end = start+chunk_size
        chunk_list.append(data[start:end])
    return chunk_list

def draw_progress_bar(val, max_val):
    max_bar_points = 50
    prog_bar_str = '['
    fill_perc = val/max_val
    empty_perc = 1-fill_perc
    fill_points = round(fill_perc*max_bar_points)
    empty_points = max_bar_points-fill_points
    for i in range(fill_points):
        prog_bar_str += '0'
    for i in range(empty_points):
        prog_bar_str += '-'
    prog_bar_str += ']'
    print(f'{prog_bar_str} | {val}/{max_val}',end='\r')

# Takes kwargs dict of data, and based on msg_type, encodes
# relevant data into a message. Data can differ, depending
# on the msg_type. Check docs for msg format and to 
# understand data layout.
def encode_message(**kwargs):
    global magic_number
    msg = int.to_bytes(magic_number,1,'little') # Byte 0 - Magic number
    msg += int.to_bytes(kwargs['msg_type'].value,1,'little') # Byte 1 - MsgType
    msg_data = b''
    
    match kwargs['msg_type']:
        case MsgType.SendReq:
            # print('SendReq')
            file_checksum = hashlib.md5(kwargs['file_data']).digest()
            file_checksum_size = len(file_checksum)
            addr_data = str.encode(kwargs['addr'])
            addr_data_size = len(addr_data)
            # print(addr_data)
            # print(list(addr_data))
            
            data_blob = addr_data+file_checksum
            data_blob_index = 18
            addr_data_offset = 0
            file_data_checksum_offset = \
                addr_data_offset+addr_data_size

            msg_data = int.to_bytes(kwargs['chunk_count'],4,'little') # Byte 6-9
            msg_data += int.to_bytes(addr_data_offset,1,'little') # Byte 10
            msg_data += int.to_bytes(addr_data_size,1,'little') # Byte 11
            msg_data += int.to_bytes(file_data_checksum_offset,1,'little') # Byte 12
            msg_data += int.to_bytes(file_checksum_size,1,'little') # Byte 13
            msg_data += int.to_bytes(len(data_blob),4,'little') # Byte 14-17
            msg_data += data_blob # Byte 18-n
            
        case MsgType.SendAccept:
            addr_data = str.encode(kwargs['addr']) 
            addr_data_size = len(addr_data)
            msg_data = addr_data_size.to_bytes(1,'little') # Byte 6
            msg_data += addr_data # Byte 7-n
            pass
        case MsgType.FilePkt:
            msg_data = int.to_bytes(kwargs['chunk_no'],4,'little') # Byte 6-9
            msg_data += int.to_bytes(kwargs['chunk_size'],4,'little') # Byte 10-13
            msg_data += kwargs['chunk_data'] # Byte 14-n
        case MsgType.FilePktAck:
            msg_data = int.to_bytes(kwargs['chunk_no'],4,'little') # Byte 6-9
            chunk_data_checksum = hashlib.md5(kwargs['chunk_data']).digest()
            msg_data += int.to_bytes(len(chunk_data_checksum),4,'little') # Byte 10-13
            msg_data += chunk_data_checksum # Byte 14-n
        case MsgType.EOFPkt:
            msg_data = int.to_bytes(
                kwargs['total_filepkts_received'],4,'little') # Byte 6-9
            file_checksum = hashlib.md5(kwargs['file_data']).digest()
            msg_data += int.to_bytes(len(file_checksum),1,'little') # Byte 10
            msg_data += file_checksum # Byte 11-n
        case _:
            pass
    msg += int.to_bytes(len(msg_data),4,'little') # Byte 2-5
    msg += msg_data # Byte 6-n
    # print(f'data_blob:{list(msg[14+18:100])}')

    return msg

# Takes a bytes object and based MsgType, decodes the data into
# a readable form, stores it into a dict, and returns the dict.
def decode_message(msg):
    global magic_number

    ret = {}
    
    msg_type = MsgType._value2member_map_[int.from_bytes(msg[1:2],'little')] # Byte 1
    data_size = int.from_bytes(msg[2:6],'little') # Byte 2-5

    if msg_type == MsgType.SendReq:
        chunk_count = int.from_bytes(msg[6:10],'little') # Byte 6-9
        addr_data_offset = msg[10] # Byte 10
        addr_data_size = msg[11] # Byte 11
        file_data_checksum_offset = msg[12] # Byte 12
        file_data_checksum_size = msg[13] # Byte 13
        data_blob_size = int.from_bytes(msg[14:18],'little') # Byte 14-17
        data_blob_index = 18
        # print((msg))

        # Byte 18-n
        addr = str(
            msg[data_blob_index+addr_data_offset:\
                data_blob_index+addr_data_offset+addr_data_size],'utf-8')
        addr = addr.split(':')
        addr = (addr[0],int(addr[1]))
        file_data_checksum = msg[data_blob_index+file_data_checksum_offset:\
            data_blob_index+file_data_checksum_offset+file_data_checksum_size]
        # print(file_data_checksum)
        # print(list(file_data_checksum))

        ret = {
            'addr':addr,
            'chunk_count':chunk_count,
            'file_checksum':file_data_checksum
        }
        # print(list(msg))
        pass
    elif msg_type == MsgType.SendAccept:
        addr_data_size = msg[6] # Byte 6
        addr_data = msg[7:7+addr_data_size] # Byte 7-n
        ret = {'addr':addr_data}
        # print(addr_data)
        # print(list(addr_data))
        pass
    elif msg_type == MsgType.FilePkt:
        chunk_no = int.from_bytes(msg[6:10],'little') # Byte 6-9
        chunk_data_size = int.from_bytes(msg[10:14],'little') # Byte 10-13
        chunk_data = msg[14:14+chunk_data_size] # Byte 14-n
        ret = {'chunk_no':chunk_no,'chunk_data':chunk_data}
        pass
    elif msg_type == MsgType.FilePktAck:
        chunk_no = int.from_bytes(msg[6:10],'little') # Byte 6-9
        # Byte 10-13
        chunk_data_checksum_size = int.from_bytes(msg[10:14],'little')
        # Byte 14-n
        chunk_data_checksum = msg[14:14+chunk_data_checksum_size]
        ret = {'chunk_data_checksum':chunk_data_checksum}
        pass
    elif msg_type == MsgType.EOFPkt:
        # Byte 6-9
        total_filepkts_recvd = int.from_bytes(msg[6:10],'little')
        file_checksum_data_size = msg[10] # Byte 10
        file_checksum = msg[11:11+file_checksum_data_size] # Byte 11-n
        ret = {'file_checksum':file_checksum}
        pass

    ret['msg_type'] = msg_type
    return ret

def send(filename, sender_addr, recvr_addr):
    global magic_number
    global sock_timeout
    data = 0
    print('Reading file...')
    with open(filename,'rb') as f:
        data = f.read()
    print('Reading complete.')
    # print('Opening socket.')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f'Binding socket to {sender_addr}')
    sock.bind(sender_addr)
    sock.settimeout(sock_timeout)
    recv_buffer_size = 1250
    file_checksum = hashlib.md5(data).digest()
    chunk_list = slice_data(data, 1024)
    chunk_count = len(chunk_list)
    state = ProgState.SendingSendReq
    curr_chunk_no = 0 # Increments each time a chunk was successfully sent.
    # Used to confirm the correct chunk data was recevied by recvr.
    curr_chunk_checksum = b'' 
    # msg = create_message(**{
    #     'msg_type':MsgType.FilePktAck,'chunk_no':curr_chunk_no,
    #     'chunk_data':chunk_list[curr_chunk_no]
    # })
    # print(list(msg))
    # dec_msg = decode_message(msg)
    # print(dec_msg)

    # Debugging code
    # ------------------------------------
    # SendAccept
    # temp_recvr_addr = ('192.168.8.103',9510)
#     temp_debug_buffer = [26, 2, 19, 0, 0, 0, 18, 49, 57, 50, 46, 49, 54, 56, 46, 56, 46, 49, 49, 49, 58, 57, 
# 53, 49, 48]
#     # FilePktAck
#     temp_debug_buffer = [26, 4, 24, 0, 0, 0, 0, 0, 0, 0, 16, 0, 0, 0, 144, 1, 80, 152, 60, 210, 79, 176, 214, 150, 63, 125, 40, 225, 127, 114]
#     temp_debug_buffer = [26, 5, 21, 0, 0, 0, 1, 0, 0, 0, 16, 144, 1, 80, 152, 60, 210, 79, 176, 214, 150, 63, 125, 40, 225, 127, 114]
#     temp_debug_buffer = bytes(temp_debug_buffer)
#     state = ProgState.AwaitingFilePktAck
#     curr_chunk_no = 0
    # ------------------------------------

    # At each iteration, based on state, program does it's job
    # and then changes state to the relevant ProgState.
    while True:
        # break
        if state == ProgState.SendingSendReq:
            # Create and send SendReq msg.
            print(f'Sending SendReq to {recvr_addr}')
            msg = encode_message(**{
                'msg_type':MsgType.SendReq,'file_data':data,
                'addr':f'{sender_addr[0]}:{str(sender_addr[1])}',
                'chunk_count':chunk_count})
            sock.sendto(msg,recvr_addr)
            # sock.sendto(b'abcdef',addr)
            # print(f'{addr[0]}:{str(addr[1])}')
            # print(len(msg))
            # Change state so at next iteration we are awaiting
            # SendAccept msg.
            state = ProgState.AwaitingSendAccept
            # break
        elif state == ProgState.AwaitingSendAccept:
            # Receive and decode SendAccept msg
            print(f'Awaiting SendAccept')
            recv_msg = sock.recvfrom(recv_buffer_size)
            ret_addr = recv_msg[1]
            recv_msg = recv_msg[0]
            
            # If data is received from any address other than recvr_addr
            # it's not meant for this program, so ignore it and continue
            # to next iteration.
            if ret_addr == recvr_addr:
                print(f'Received SendAccept from {recvr_addr}')
            else:
                continue

            # recv_msg = temp_debug_buffer
            if recv_msg[0] != magic_number:
                continue
            decoded_data = decode_message(recv_msg)
            # print(decoded_data)
            if decoded_data['msg_type'] == MsgType.SendAccept:
                # SendAccept received. Change state so we can start
                # sending file pkts.
                state = ProgState.SendingFilePkt
            # print(decoded_data)
            # break
        elif state == ProgState.SendingFilePkt:
            # Create and send FilePkt msg.
            # print('SendingFilePkt')
            msg = encode_message(**{
                    'msg_type':MsgType.FilePkt,'chunk_no':curr_chunk_no,
                    'chunk_size':len(chunk_list[curr_chunk_no]),
                    'chunk_data':chunk_list[curr_chunk_no]})
            sock.sendto(msg,recvr_addr)
            # print(f'curr_chunk_no:{curr_chunk_no}',end='\r')
            # print(list(msg))
            curr_chunk_checksum = hashlib.md5(chunk_list[curr_chunk_no]).digest()
            # Change state so next iteration we're awaiting FilePktAck
            state = ProgState.AwaitingFilePktAck
            # break
        elif state == ProgState.AwaitingFilePktAck:
            # Receive and decode FilePktAck
            # print('AwaitingFilePktAck')
            recv_msg = sock.recvfrom(recv_buffer_size)
            recv_msg = recv_msg[0]
            # recv_msg = temp_debug_buffer
            if recv_msg[0] != magic_number:
                continue
            decoded_data = decode_message(recv_msg)
            # print(f'curr_chunk_no:{curr_chunk_no}',end='\r')
            # print(decoded_data)
            
            # If FilePktAck is received...
            if decoded_data['msg_type'] == MsgType.FilePktAck:
                # If chunk is not the last chunk received chunk checksum
                # is same as stored chunk checksum...
                if curr_chunk_no < len(chunk_list) and \
                    decoded_data['chunk_data_checksum'] == curr_chunk_checksum:
                    draw_progress_bar(curr_chunk_no+1,chunk_count)
                    # print(f'Chunks sent: {curr_chunk_no+1}',end='\r')
                    # Increment curr_chunk_no.
                    curr_chunk_no += 1
                # Change state so next chunk can be sent.
                state = ProgState.SendingFilePkt
            # Else if EOFPkt is received...
            elif decoded_data['msg_type'] == MsgType.EOFPkt:
                # If received file checksum is same as stored file checksum...
                if decoded_data['file_checksum'] == file_checksum:
                    draw_progress_bar(curr_chunk_no+1,chunk_count)
                    # print(f'Chunks sent: {curr_chunk_no+1}')
                    print('\nTransfer successful')
                    # print(f'Chunks sent: {curr_chunk_no+1}')
                # Else...
                else:
                    print('Transfer failed')
                break
            # print(f'Chunks sent: {curr_chunk_no+1}',end='\r')

    # print(list(msg))
    # print('Closing socket.')
    sock.close()
    pass

def recv(filename, sender_addr, recvr_addr):
    global magic_number
    global sock_timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(recvr_addr)
    sock.settimeout(sock_timeout)
    recv_buffer_size = 1250
    # addr = ('192.168.8.103',9050)
    print(f'Binding socket to {recvr_addr}')
    file_checksum = b''
    chunk_list = [] # This list gets populated once SendReq is recv'd
    chunk_count = 0
    state = ProgState.AwaitingSendReq
    curr_chunk_no = 0

    sendreq_chunk_count = 0
    sendreq_file_checksum = b''
    # Debugging code
    # ----------------------------------------------
    # temp_sender_addr = ('192.168.8.111',9510)
    # SendReq
#     temp_debug_buffer = [26, 1, 46, 0, 0, 0, 1, 0, 0, 0, 0, 18, 18, 16, 34, 0, 0, 0, 49, 57, 50, 46, 49, 54, 
# 56, 46, 56, 46, 49, 48, 51, 58, 57, 53, 49, 48, 144, 1, 80, 152, 60, 210, 79, 176, 214, 150, 63, 125, 40, 225, 127, 114]
#     # FilePkt
#     temp_debug_buffer = [26, 3, 11, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 97, 98, 99]
#     temp_debug_buffer = bytes(temp_debug_buffer)
#     state = ProgState.SendingFilePktAck
#     chunk_list = [b'abc']
#     sendreq_chunk_count = 1
    # ----------------------------------------------

    # At each iteration, based on state, program does it's job
    # and then changes state to the relevant ProgState.
    while True:
        # break
        if state == ProgState.AwaitingSendReq:
            # Receive and decode SendReq
            print(f'AwaitingSendReq')
            recv_msg = sock.recvfrom(recv_buffer_size)
            ret_addr = recv_msg[1]
            recv_msg = recv_msg[0]

            # If data is received from any address other than sender_addr
            # it's not meant for this program, so ignore it and continue
            # to next iteration.
            if ret_addr == sender_addr:
                print(f'Received SendReq from {sender_addr}')
            else:
                continue

            # print(recv_msg)
            # recv_msg = temp_debug_buffer
            if recv_msg[0] != magic_number:
                continue
            decoded_data = decode_message(recv_msg)
            # print(decoded_data['msg_type'])
            # If SendReq was received...
            if decoded_data['msg_type'] == MsgType.SendReq:
                # Use it to set initial values for variables
                sendreq_chunk_count = decoded_data['chunk_count']
                sendreq_file_checksum = decoded_data['file_checksum']
                for i in range(sendreq_chunk_count):
                    chunk_list.append([0])
                # Change state so next iteration, we send SendAccept.
                state = ProgState.SendingSendAccept
                # print(decoded_data['msg_type'])
            # print(decoded_data)
            # break
        elif state == ProgState.SendingSendAccept:
            # Create and send SendAccept
            print('SendingSendAccept')
            msg = encode_message(**{
                'msg_type':MsgType.SendAccept,
                'addr':f'{sender_addr[0]}:{str(sender_addr[1])}'})
            sock.sendto(msg, sender_addr)
            # print(list(msg))
            # Change state so next iteration we start receiving FilePkts.
            state = ProgState.AwaitingFilePkt
            # break
        elif state == ProgState.AwaitingFilePkt:
            # Receive and decode FilePkt.
            # print('AwaitingFilePkt')
            recv_msg = sock.recvfrom(recv_buffer_size)
            recv_msg = recv_msg[0]
            # recv_msg = temp_debug_buffer
            if recv_msg[0] != magic_number:
                continue
            decoded_data = decode_message(recv_msg)
            # If FilePkt was received...
            if decoded_data['msg_type'] == MsgType.FilePkt:
                # Set curr_chunk_no and add chunk to chunk_list.
                curr_chunk_no = decoded_data['chunk_no']
                # print(curr_chunk_no)
                chunk_list[curr_chunk_no] = decoded_data['chunk_data']

                # Change state so next iteration we send FilePktAck.
                state = ProgState.SendingFilePktAck
            # print(decoded_data)
            # break
        elif state == ProgState.SendingFilePktAck:
            # Create and send FilePktAckt
            # print('SendingFilePkt')
            msg = b''
            # If curr_chunk_no is last chunk...
            if curr_chunk_no == sendreq_chunk_count-1:
                # Create file_data object out of chunks in chunk_list
                file_data = b''
                for i in range(len(chunk_list)):
                    file_data += chunk_list[i]

                # Check if received file data's checksum matches checksum
                # that was received in SendReq. If it does, file data 
                # transfer was successful.
                if hashlib.md5(file_data).digest() == sendreq_file_checksum:
                    # Create and send EOFPkt msg
                    msg = encode_message(**{
                        'msg_type':MsgType.EOFPkt,'total_filepkts_received':curr_chunk_no+1,
                        'file_data':file_data
                    })
                    sock.sendto(msg,sender_addr)
                    draw_progress_bar(curr_chunk_no+1,sendreq_chunk_count)
                    # print(f'Chunks received:{curr_chunk_no+1}')
                    print(f'\nFile received. File Data Size: {len(file_data)}.')
                    # print(list(msg))

                    # Create (if needed) and write data to it.
                    with open(filename, 'wb+') as f:
                        f.write(file_data)
                    # break loop so we can exit program.
                    break
            # Else if curr_chunk_no is not last chunk.
            else:
                # Create and send FilePktAck msg.
                msg = encode_message(**{
                    'msg_type':MsgType.FilePktAck,'chunk_no':curr_chunk_no,
                    'chunk_data':chunk_list[curr_chunk_no]
                })
                sock.sendto(msg,sender_addr)
                # print(list(msg))
                draw_progress_bar(curr_chunk_no+1,sendreq_chunk_count)
                # print(f'Chunks received:{curr_chunk_no+1}',end='\r')

                # Change state so next iteration we await another FilePkt.
                state = ProgState.AwaitingFilePkt
            # break
        # break

    # print('Closing socket.')
    sock.close()
    pass

if __name__ == '__main__':
    # Read arguments and prepare variables.
    
    if sys.argv[1] == 'help':
        help_msg = 'Send or receive files over UDP. Start the receiver first, then the sender.\n\n\
Usage:\n\
Mode: send/recv\n\
Filename\n\
Sender address: (IP:Port)\n\
Receiver address: (IP:Port)\n\n\
Example:\n\
python file_transfer.py send somefile01.txt 192.168.8.111:9510 192.168.8.103:9510\n\
python file_transfer.py recv somefile01.txt 192.168.8.111:9510 192.168.8.103:9510\n\n\
NOTE:\n\
Socket timeout in both modes is set to 20 seconds by default. If you\'re sending a big file and the program might take longer than 10 seconds to read and process the data, consider increasing the value of sock_timeout in the script, to avoid reaching socket timeout.'

        print(help_msg)
    else:
        try:
            mode = sys.argv[1] # mode
            filename = sys.argv[2] # file name
            addr_temp = sys.argv[3].split(':') # sender addr
            sender_addr = (addr_temp[0],int(addr_temp[1]))
            addr_temp = sys.argv[4].split(':') # recvr addr
            recvr_addr = (addr_temp[0],int(addr_temp[1]))

            if mode == 'send':
                send(filename, sender_addr, recvr_addr)
            elif mode == 'recv':
                recv(filename, sender_addr, recvr_addr)
        except Exception as e:
            # print(f'Incorrect arguments')
            print(e)
    # write_dummy_data()
    
