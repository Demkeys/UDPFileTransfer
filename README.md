# UDPFileTransfer
Send or receive files over UDP. Start the receiver first, then the sender.

------------------------------------------------------

## Usage:
- Mode: send, recv
- Filename
- Sender address (IP:Port)
- Recvr address (IP:Port)

## Example:
```python file_transfer.py send somefile01.txt 192.168.8.111:9510 192.168.8.103:9510```

```python file_transfer.py recv somefile01.txt 192.168.8.111:9510 192.168.8.103:9510```

## NOTE:
Socket timeout in both modes is set to 10 seconds by default. If you're sending a big file and the program might take longer than 10 seconds to read and process the data, consider increasing the value of sock_timeout in the script, to avoid reaching socket timeout.

------------------------------------------------------
## Program flow:
- Receiver starts and waits for SendReq.
- Sender starts, reads and process file data, and sends SendReq containing chunk count, file checksum and other other data.
- Receiver receives SendReq, stores the data and sends SendAccept.
- Sender receives SendAccept and sends FilePkt containing chunk data.
- Receiver receives FilePkt and sends FilePktAck containing chunk checksum. Sender will use this checksum to confirm that the correct chunk data was received by receiver.
- Previous two steps repeat until receiver has received last FilePkt.
- Upon receiving last FilePkt, receiver sends EOFPkt, writes data to file and terminates. EOFPkt contains file data checksum.
- Sender receives EOFPkt, confirms whether the file data checksum matches, and terminates.
------------------------------------------------------
## Message Format:
- Byte 0: Magic Number
- Byte 1: MsgType: SendReq, SendAccept, FilePkt, FilePktAck, EOFPkt
- Byte 2-5: Data Size
- Byte 6-n: Data (depends on MsgType)
    - SendReq
        - Byte 6-9: Total number of FilePkts
        - Byte 10: Address Data Offset
        - Byte 11: Address Data Size
        - Byte 12: FileDataChecksum Offset
        - Byte 13: FileDataChecksum Size
        - Byte 14-17: DataBlob Size
        - Byte 18-n: Data Blob.
            - NOTE: Offsets and sizes will help you determine how to read data from blob. Offsets are relative to starting position of data blob.
            - General layout: Address Data | FileDataChecksum
    - SendAccept
        - Byte 6: Address Data Size
        - Byte 7-n: Adress Data
    - FilePkt
        - Byte 6-9: ChunkNumber
        - Byte 10-13: ChunkSize
        - Byte 14-n: ChunkData
    - FilePktAck
        - Byte 6-9: ChunkNumber
        - Byte 10-13: ChunkDataChecksumSize
        - Byte 14-n: ChunkDataChecksum (MD5)
    - EOFPkt
        - Byte 6-9: Total FilePkts received
        - Byte 10: FileDataChecksumSize
        - Byte 11-n: FileDataChecksum (MD5, full file data)
