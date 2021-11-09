class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except:
            raise IOError
        self.frameNum = 0
        
    def totalFrame(self):
        """Get total frame."""
        data = self.file.read(5)
        count = 0
        while data:
         # Get the framelength from the first 5 bits
            if data:
                framelength = int(data)

                # Read the current frame
                data = self.file.read(framelength)

                count += 1
            data = self.file.read(5)
        return count
        
    def nextFrame(self):
        """Get next frame."""
        data = self.file.read(5) # Get the framelength from the first 5 bits
        if data: 
            framelength = int(data)
                            
            # Read the current frame
            data = self.file.read(framelength)
            self.frameNum += 1
        return data

    def skipFrame(self, limit, skipNo):
        """Get next frame."""
        data = self.file.read(0)  # Get the framelength from the first 5 bits
        if skipNo + self.frameNum > limit:
            skipNo = limit - self.frameNum
        for x in range(skipNo):
            # Get the framelength from the first 5 bits
            data = self.file.read(5)
            if data:
                framelength = int(data)
                # Read the last 30 frame from current
                data = self.file.read(framelength)
                self.frameNum += 1
            if self.frameNum + 1 == limit:
                break
        return data

    def backFrame(self, skipNo):
        """Get back frame."""
        self.file.seek(0)
        temp = self.frameNum
        self.frameNum = 0
        data = self.file.read(0)
        for x in range(temp - skipNo):
            # Get the framelength from the first 5 bits
            data = self.file.read(5)
            if data:
                framelength = int(data)
                # Read the current frame
                data = self.file.read(framelength)
                self.frameNum += 1

        return data
        
    def frameNbr(self):
        """Get frame number."""
        return self.frameNum
    
