from tkinter import *
import tkinter.messagebox
tkinter.messagebox
from tkinter import messagebox 
tkinter.messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from datetime import datetime

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"



class Client:

    SETUP_STR = 'SETUP'
    PLAY_STR = 'PLAY'
    PAUSE_STR = 'PAUSE'
    TEARDOWN_STR = 'TEARDOWN'
    DESCRIBE_STR = 'DESCRIBE'
    NEXT_STR = 'NEXT'
    BACK_STR = 'BACK'
    INIT = 0
    READY = 1
    PLAYING = 2

    state = INIT
    
    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    DESCRIBE = 4
    NEXT = 5
    BACK = 6

    totalTime = 0
    RTSP_VER = "RTSP/1.0"
    TRANSPORT = "RTP/UDP"
    
    
    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        self.numLatePacket=0
        print("Initial the movie.")
        self.setupMovie()
        self.intervalTime = 0 # ms
        self.statTotal_bytes = 0
    def createWidgets(self):
        """Build GUI."""
        # Create slider
        self.slider = ttk.Scale(self.master, orient=HORIZONTAL, from_=0, to_=100)
        self.slider.grid(row=1, column=0, columnspan=3,sticky=W+E+N+S, padx=2, pady=2)
        self.slider_text = Label(self.master, text='0')
        self.slider_text.grid(row=1, column=3, padx=2, pady=2)

        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=2, column=0, padx=2, pady=2)
        
        # Create Play button		
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=2, column=1, padx=2, pady=2)
        
        # Create Pause button			
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=2, column=2, padx=2, pady=2)
        
        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] =  self.exitClient
        self.teardown.grid(row=2, column=3, padx=2, pady=2)
        
        # Create Describe button 
        self.describe = Button(self.master, width=20, padx=3, pady=3)
        self.describe["text"] = "Describe"
        self.describe["command"] =  self.describeMovie 
        self.describe.grid(row=3, column=0, padx=2, pady=2)

        # Create Next button
        self.next = Button(self.master, width=20, padx=3, pady=3)
        self.next["text"] = "Backward"
        self.next["command"] = self.backMovie
        self.next.grid(row=3, column=1, padx=2, pady=2)

        # Create Back button
        self.back = Button(self.master, width=20, padx=3, pady=3)
        self.back["text"] = "FastForward"
        self.back["command"] = self.nextMovie
        self.back.grid(row=3, column=2, padx=2, pady=2)


        # Create a label to display the movie
        self.label = Label(self.master, height=19)# sticky=W+E+N+S
        self.label.grid(row=0, columnspan=4, sticky=W+E+N+S,padx=5,pady=5) 

        plt_label ="Packet_loss (%)"
        self.label1=Label(text=plt_label,width=20,background="green").grid(row=5,column=0)
        vdr_label ="video_data_rate (bytes/s)"
        self.label2=Label(text=vdr_label,width=20,background="green").grid(row=6,column=0)

        describe_label = "DESCRIBE response"
        self.label3=Label(text=describe_label,width=20,background="yellow").grid(row=7,column=0)
    
    def updateSlider(self, value):
        self.slider['value'] = value
        m1, s1 = divmod(value, 60)
        m2, s2 = divmod(self.totaltime, 60)
        self.slider_text.config(text=f'{m1:02d}:{s1:02d}' + f' : {m2:02d}:{s2:02d}')
        self.slider.config(to=self.totaltime)

    def nextMovie(self):
        if not self.state == self.INIT:
            self.sendRtspRequest(self.NEXT)

    def backMovie(self):
        if not self.state == self.INIT:
            self.sendRtspRequest(self.BACK)

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)
    
    def exitClient(self):
        """Teardown button handler."""
        Packet_loss = self.computePercentLoss(self.frameNbr+self.numLatePacket,self.numLatePacket)
        print(self.frameNbr + self.numLatePacket)
        print(self.numLatePacket)
        print("packet loss rate is : "+str(Packet_loss) + " %")
        print(self.statTotal_bytes)
        print(self.intervalTime)
        video_data_rate = self.computeRateKBs(self.statTotal_bytes,self.intervalTime)
        print("video data rate is : "+str(video_data_rate) + " bytes/s")
        self.sendRtspRequest(self.TEARDOWN)		
        self.master.destroy() # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
    
    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)
    
    def describeMovie(self):
        """Describe button handler."""
        self.sendRtspRequest(self.DESCRIBE)
            

    def listenRtp(self):		
        """Listen for RTP packets."""
        start = datetime.now() 
        end = datetime.now()
        total_bytes = 0
        while True:
            try:
                print("LISTENING...")
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)
                    # rtpPacket.
                    currFrameNbr = rtpPacket.seqNum()
                    print ("CURRENT SEQUENCE NUM: " + str(currFrameNbr))
                    if (currFrameNbr-self.frameNbr)!=1:
                        self.numLatePacket+=1
                    if currFrameNbr > self.frameNbr: # Discard the late packet
                        self.frameNbr = currFrameNbr
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
                        self.updateSlider(int(self.frameNbr/15))
                    end = datetime.now()
                    total_time = self.time_different(end,start)
                    total_bytes += rtpPacket.getPayload_length()

                    Packet_loss = self.computePercentLoss(self.frameNbr+self.numLatePacket,self.numLatePacket)
                    video_data_rate = self.computeRateKBs(total_bytes,total_time)
                    self.label1 = Label(text=str(Packet_loss),width=20,relief=tkinter.RIDGE,background="yellow").grid(row=5,column=1)
                    self.label2 = Label(text=str(video_data_rate),width=20,relief=tkinter.RIDGE,background="yellow").grid(row=6,column=1)
                    
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.isSet(): 
                    break
                
                # Upon receiving ACK for TEARDOWN request,
                # close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break
        end = datetime.now()
        total_time = self.time_different(end,start)
        self.intervalTime += total_time
        print("Total: "+str(self.intervalTime))
        self.statTotal_bytes += total_bytes

        # self.intervalTime+=total_time
                    
    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()
        
        return cachename
    
    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image = photo, height=288) 
        self.label.image = photo
        
    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
    
    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""	
        #-------------
        # TO COMPLETE
        #-------------
        
        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
                
            # Update RTSP sequence number.
            self.rtspSeq+=1
            
            # Write the RTSP request to be sent.
            request = "%s %s %s" % (self.SETUP_STR,self.fileName,self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nTransport: %s; client_port= %d" % (self.TRANSPORT,self.rtpPort)
            
            self.requestSent = self.SETUP
            
            # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
        
            # Update RTSP sequence number.
            self.rtspSeq+=1
        
            # Write the RTSP request to be sent.
            request = "%s %s %s" % (self.PLAY_STR,self.fileName,self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nSession: %d"%self.sessionId
                
            # Keep track of the sent request.
            self.requestSent = self.PLAY
            
            
            # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
        
            # Update RTSP sequence number.
            self.rtspSeq+=1
            
            request = "%s %s %s" % (self.PAUSE_STR,self.fileName,self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nSession: %d"%self.sessionId
            
            self.requestSent = self.PAUSE
            
            # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
        
            # Update RTSP sequence number.
            self.rtspSeq+=1
            
            # Write the RTSP request to be sent.
            request = "%s %s %s" % (self.TEARDOWN_STR, self.fileName, self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nSession: %d" % self.sessionId
            
            self.requestSent = self.TEARDOWN

            #DESCRIBE request
        elif requestCode == self.DESCRIBE and self.state == self.READY:
            #Update RTSP sequence number
            self.rtspSeq+=1
            # Write the RTSP request to be sent.
            request = "%s %s %s" % (self.DESCRIBE_STR,self.fileName,self.RTSP_VER)
            request+="\nCSeq: %d" % self.rtspSeq
            request+="\nAccept: application/sdp"

            # request+="\nSession: %d"%self.sessionId 

            self.requestSent = self.DESCRIBE
        
        elif requestCode == self.NEXT and not self.state == self.INIT:
            #Update RTSP sequence number
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            request = "%s %s %s" % (self.NEXT_STR, self.fileName, self.RTSP_VER)
            request += "\nCSeq: %d" % self.rtspSeq

            # request+="\nSession: %d"%self.sessionId
            self.requestSent = self.NEXT
        
        elif requestCode == self.BACK and not self.state == self.INIT:
            #Update RTSP sequence number
            self.frameNbr = 0
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            request = "%s %s %s" % (self.BACK_STR, self.fileName, self.RTSP_VER)
            request += "\nCSeq: %d" % self.rtspSeq

            # request+="\nSession: %d"%self.sessionId
            self.requestSent = self.BACK
            
        else:
            return
        
        # Send the RTSP request using rtspSocket.
        self.rtspSocket.send(request.encode())
        
        print ('\nData Sent:\n' + request)
    
    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)
            
            if reply: 
                self.parseRtspReply(reply)
            
            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break
    
    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.decode().split('\n')
        seqNum = int(lines[1].split(' ')[1])
        print(seqNum)

        #DESCRIBE REQUEST
        if self.requestSent==self.DESCRIBE:
            self.display_description(data)
            self.state=self.READY

        elif self.requestSent==self.TEARDOWN:
            self.state = self.INIT
            self.teardownAcked=1
            return
        # Process only if the server reply's sequence number is the same as the request's
        elif (seqNum == self.rtspSeq) and (self.requestSent!=self.DESCRIBE):
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session
            
            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200: 
                    if self.requestSent == self.SETUP:
                        #-------------
                        # Update RTSP state.
                        self.state = self.READY
                        self.totaltime = round(int(lines[4])/15)
                        # Open RTP port.
                        self.openRtpPort() 
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        
                        # The play thread exits. A new thread is created on resume.
                        self.playEvent.set()
                    elif self.requestSent == self.NEXT:
                        pass
                    elif self.requestSent == self.BACK:
                        pass
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        
                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        
        # Create a new datagram socket to receive RTP packets from the server
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Set the timeout value of the socket to 0.5sec
        self.rtpSocket.settimeout(0.5)
        
        try:
            # Bind the socket to the address using the RTP port given by the client user.
            self.state=self.READY
            self.rtpSocket.bind(('',self.rtpPort))
        except:
            messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else: # When the user presses cancel, resume playing.
            self.playMovie()

    def computePercentLoss(self,nbLostAndRecv,nbLost):
        if nbLostAndRecv ==0:
            return 0
        else:
            return (100*nbLost)/nbLostAndRecv

    def computeRateKBs(self,nBytes,intervalMs):
        if intervalMs==0:
            return 0
        else:
            return nBytes/intervalMs

    def time_different(self,dt2, dt1):
        timedelta = dt2 - dt1
        return timedelta.days * 24 * 3600 + timedelta.seconds
        
    def display_description(self,recvData):
        recvData = recvData.decode().split('\n')
        lenOfRecvData = len(recvData)
        for i in range(0,lenOfRecvData):
            c = recvData[i]
            Label(text=c).grid(row=int(i+8),column=0,sticky=NW)
