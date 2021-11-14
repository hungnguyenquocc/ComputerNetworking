from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket


class ServerWorker:
        
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    DESCRIBE = 'DESCRIBE'
    NEXT = 'NEXT'
    BACK = 'BACK'
    SWITCH = 'SWITCH'
    
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    skipNo = 0
    totalFrame = 0
    request = ''

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2
    
    list = "\n movie.Mjpeg"
    clientInfo = {}
    
    def __init__(self, clientInfo):
        self.clientInfo = clientInfo
        
    def run(self):
        threading.Thread(target=self.recvRtspRequest).start()
    
    def recvRtspRequest(self):
        """Receive RTSP request from the client."""
        connSocket = self.clientInfo['rtspSocket'][0]
        while True:            
            data = connSocket.recv(256)
            if data:
                print ("\nDATA RECEIVED: \n", data.decode())
                self.processRtspRequest(data)
    
    def processRtspRequest(self, data):
        """Process RTSP request sent from the client."""
        # Get the request type
        request = data.decode().split('\n') #của đề bài
        # request = data.split('\n')
        line1 = request[0].split(' ')
        requestType = line1[0]
        # Get the media file name
        filename = line1[1]
        
        # Get the RTSP sequence number 
        seq = request[1].split(' ')
        # Process SETUP request
        if requestType == self.SETUP:
            self.clientInfo['isDescribe-request']=False
            if self.state == self.INIT:
                # Update state
                print ("\nPROCESSING SETUP\n")
                
                try:
                    self.clientInfo['videoStream'] = VideoStream(filename)
                    self.totalFrame = self.clientInfo['videoStream'].totalFrame()
                    self.clientInfo['videoStream'] = VideoStream(filename)
                    self.state = self.READY
                    self.request = 'SETUP'

                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                
                # Generate a randomized RTSP session ID
                self.clientInfo['session'] = randint(100000, 999999)
                self.clientInfo['filename']=filename
                self.clientInfo['length'] = len(data)
                # Send RTSP reply
                self.replyRtsp(self.OK_200, seq[1])
                
                # Get the RTP/UDP port from the last line
                self.clientInfo['rtpPort'] = request[2].split(' ')[3]

        # Process PLAY request 		
        elif requestType == self.PLAY:
            if self.state == self.READY:
                print ("\nPROCESSING PLAY\n")
                self.state = self.PLAYING
                
                # Create a new socket for RTP/UDP
                self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                
                self.replyRtsp(self.OK_200, seq[1])
                
                # Create a new thread and start sending RTP packets
                self.clientInfo['event'] = threading.Event()
                self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
                self.clientInfo['worker'].start()
        
        # Process PAUSE request
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print ("\nPROCESSING P A U S E\n")
                self.state = self.READY
                
                self.clientInfo['event'].set()
            
                self.replyRtsp(self.OK_200, seq[1])

        elif requestType == self.NEXT:
            print("\nProcessing N E X T\n")
            self.skipNo+=1
            self.replyRtsp(self.OK_200,seq[1])
            self.request = 'NEXT'

        elif requestType == self.BACK:
            print("processing B A C K\n")
            self.skipNo += 1
            self.replyRtsp(self.OK_200, seq[1])
            self.request = 'BACK'

        # Process TEARDOWN request
        elif requestType == self.TEARDOWN:
            print ("PROCESSING TEARDOWN\n")

            self.clientInfo['event'].set()
            
            self.replyRtsp(self.OK_200, seq[1])
            
            # Close the RTP socket
            self.clientInfo['rtpSocket'].close()
        # Process DESCRIBE request
        elif requestType == self.DESCRIBE:
            self.clientInfo['isDescribe-request']=True
            self.replyRtsp(self.OK_200,seq[1])

    def sendRtp(self):
        """Send RTP packets over UDP."""
        while True:
            self.clientInfo['event'].wait(0.05) 
            # Stop sending if request is PAUSE or TEARDOWN
            if self.clientInfo['event'].isSet(): 
                break
            if self.request == self.NEXT:
                data = self.clientInfo['videoStream'].skipFrame(self.totalFrame, self.skipNo*75)
                self.skipNo = 0
                self.request = ''
            elif self.request == self.BACK:
                data = self.clientInfo['videoStream'].backFrame(self.skipNo*75)
                self.skipNo = 0
                self.request = ''
            else:
                data = self.clientInfo['videoStream'].nextFrame()
            if data: 
                frameNumber = self.clientInfo['videoStream'].frameNbr()
                try:
                    address = self.clientInfo['rtspSocket'][1][0]
                    port = int(self.clientInfo['rtpPort'])
                    self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber),(address,port))
                except:
                    print ("Connection Error")

    def makeRtp(self, payload, frameNbr):
        """RTP-packetize the video data."""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26 # MJPEG type
        seqnum = frameNbr
        ssrc = 0 
        
        rtpPacket = RtpPacket()
        
        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
        
        return rtpPacket.getPacket()
        
    def replyRtsp(self, code, seq):
        """Send RTSP reply to the client."""
        reply=''
        if code == self.OK_200:
            #print "200 OK"
            
            if self.clientInfo['isDescribe-request']==True:
                #first
                segment1 =  'RTSP/1.0 200 OK\nCSeq: ' + seq
                segment2 = '\nv=1.0'
                segment3 = '\nm=video '+ str(self.clientInfo['rtpPort']) + ' RTP/AVP ' + '26'
                segment4 = '\nSession ID =' + str(self.clientInfo['session'])
                segment5 = '\na=mimetype:string;\"video/MJPEG\"'
                first_body = segment1+segment2+segment3+segment4+segment5

                #second
                segment6 = '\nContent-Base: '+self.clientInfo['filename']
                segment7 = '\nContent-Type: ' + 'application/sdp'
                segment8 = '\nContent-Length: ' + str(len(first_body))
                second_body = segment6+segment7+segment8
                reply = first_body+second_body
            
            else:
                reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
                if self.request == self.SETUP:
                    reply += self.list + f'\n{self.totalFrame}'

            connSocket = self.clientInfo['rtspSocket'][0]
            connSocket.send(reply.encode())
            print(reply)
        # Error messages
        elif code == self.FILE_NOT_FOUND_404:
            print ("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print ("500 CONNECTION ERROR")
