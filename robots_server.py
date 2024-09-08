import socket
import threading


# Hashing key pairs
keyPairs = [[23019, 32037], [32037, 29295], [18789, 13603], [16443, 29533], [18189, 21952]]


# Readability constants

# Directions
NORTH = 0
EAST = 90
SOUTH = 180
WEST = 270

# Coordinate axes
X = 0
Y = 1

# Collision limit
COLLISION_LIMIT = 20

# Timeouts
NORMAL_TIMEOUT = 1
RECHARGING_TIMEOUT = 5

# Response lengths
FULL_POWER = 12
USERNAME = 20
AUTHENTICATION_KEY = 5
CLIENT_CONFIRMATION = 7
MOVEMENT_CONFIRMATION = 12
MESSAGE = 100


class Robot:


	def __init__(self, socket):
		'''Assigns connection socket and sets the default parameters.'''
		
		self.socket = socket  # Connection socket
		self.currentResponse = ""
		self.responsesQueue = []
		self.remainder = ""  # Unfinished part of a message transition (with no delimiter received)
		self.coordinates = [0, 0]
		self.direction = NORTH  # Robot direction as compass heading: NORTH-0, EAST-90, SOUTH-180, WEST-270
		self.collisions = 0
		
		
	def recharge(self):
		self.currentResponse = "RECHARGING"
		# Extend socket timeout for reacharging
		self.socket.settimeout(RECHARGING_TIMEOUT)  
		# Wait for FULL POWER response
		self.getResponse(FULL_POWER)  
		# Reset timeout to normal state
		self.socket.settimeout(NORMAL_TIMEOUT)


	def getResponse(self, expectedLength):
		'''
		Gets next response from the server. Optimized expected length checking. 
		Set expectedLength to -1 if the expected length of awaited response is unknown.
		'''
		
		# If responses queue is empty, load some new responses from the socket there
		if not self.responsesQueue:
			# Take remainder from last robot response
			message = self.remainder
			# Add 512 bytes received from the server
			message += self.socket.recv(512).decode()

			# While message is not complete
			while "\a\b" not in message:
				# Expected length optimization
				if expectedLength != -1 and len(message) >= expectedLength:
					raise Exception("301 SYNTAX ERROR\a\b")

				# Get message's continuation
				message += self.socket.recv(512).decode()

			# Split message by delimiter
			self.responsesQueue = message.split("\a\b")
			# Set remainder to be the last part of the splitted message
			self.remainder = self.responsesQueue[-1]
			# Delete remainder from the queue
			del self.responsesQueue[-1]  

		# Save next element in the queue as the new response
		nextResponse = self.responsesQueue[0]
		# Remove it from the queue
		del self.responsesQueue[0]

		# Logic check: after RECHARGING response only FULL POWER is valid
		if self.currentResponse == "RECHARGING" and nextResponse != "FULL POWER":
			raise Exception("302 LOGIC ERROR\a\b")

		# RECHARGING response logic
		elif nextResponse == "RECHARGING":
			self.recharge()
			# Get the actual next response
			self.getResponse(expectedLength) 

		# Default response logic
		else:
			self.currentResponse = nextResponse

	
	def authenticate(self):
		'''Authenticates a newly connected robot.'''
		
		# Get robot's username
		self.getResponse(USERNAME)
		username = self.currentResponse

		# Username format validation
		if len(username) > 18:
			raise Exception("301 SYNTAX ERROR\a\b")

		# Get authentication key
		self.socket.send("107 KEY REQUEST\a\b".encode())
		self.getResponse(AUTHENTICATION_KEY)
		key = self.currentResponse

		# Authentication key format validation
		if not key.isdigit():
			raise Exception("301 SYNTAX ERROR\a\b")

		# Convert key to integer
		key = int(key)

		# Key range validation
		if key < 0 or key > 4:
			raise Exception("303 KEY OUT OF RANGE\a\b")

		# Calculate username hash
		usernameHash = 0
		for i in username:
			usernameHash += ord(i)
		usernameHash *= 1000
		usernameHash %= 65536

		# Calculate server-side hash and send it to the client
		serverHash = (usernameHash + keyPairs[key][0]) % 65536
		self.socket.send(f"{serverHash}\a\b".encode())

		# Get client confirmation
		self.getResponse(CLIENT_CONFIRMATION)
		clientConfirmation = self.currentResponse

		# Confirmation format validation
		if len(clientConfirmation) > 5 or not clientConfirmation.isdigit():
			raise Exception("301 SYNTAX ERROR\a\b")

		# Convert client confirmation to integer
		clientConfirmation = int(clientConfirmation)

		# Compute expected client hash
		clientHash = (usernameHash + keyPairs[key][1]) % 65536

		# Compare client confirmation and expected client hash
		if clientConfirmation != clientHash:
			raise Exception("300 LOGIN FAILED\a\b")

		# Confirm authentication's completion
		self.socket.send("200 OK\a\b".encode())

	
	def setCoordinates(self):
		'''Sets robot's coordinates. Used after some movement command like TURN or MOVE.'''
		
		# Receive message in the format "OK X Y", where X and Y are robot's coordinates
		self.getResponse(MOVEMENT_CONFIRMATION)

		# Split message by spaces
		message = self.currentResponse.split(" ")

		# Check the format
		if len(message) != 3 or message[0] != "OK":
			raise Exception("301 SYNTAX ERROR\a\b")

		# Try converting coordinates into integers and set new coordinates
		try:
			self.coordinates = [int(message[1]), int(message[2])]
		except:
			raise Exception("301 SYNTAX ERROR\a\b")

	
	def getInitialConditions(self):
		'''Gets starting position and heading direction.'''
		
		# Turn the robot to get initial coordinates
		self.socket.send("103 TURN LEFT\a\b".encode())
		self.setCoordinates()

		# Save initial coordinates
		oldX = self.coordinates[X]
		oldY = self.coordinates[Y]

		# Move the robot to get direction
		self.socket.send("102 MOVE\a\b".encode())
		self.setCoordinates()

		# Direction calculation
		if self.coordinates[Y] == oldY:
			# Robot moved to the right      -> EAST
			if self.coordinates[X] > oldX:
				self.direction = EAST
			# Robot moved to the left       -> WEST
			elif self.coordinates[X] < oldX:
				self.direction = WEST

			# Robot is at the same position -> collision, try again
			else:
				self.collisions += 1
				self.getInitialConditions()
		else:
			# Robot moved up                -> NORTH
			if self.coordinates[Y] > oldY:
				self.direction = NORTH
			# Robot moved down              -> SOUTH
			else:
				self.direction = SOUTH

	
	def rotate(self, finalDirection):
		'''Rotates the robot until it faces the required direction.'''
		
		while self.direction != finalDirection:
			self.socket.send("104 TURN RIGHT\a\b".encode())
			self.setCoordinates()
			self.direction = (self.direction + 90) % 360

	
	def avoidObstacle(self, axis):
		'''
		Avoids an obstacle by going around the left of it. 
		Provided axis must correspond to the moving axis of the robot.
		'''
		
		self.socket.send("103 TURN LEFT\a\b".encode())
		self.setCoordinates()

		self.socket.send("102 MOVE\a\b".encode())
		self.setCoordinates()

		self.socket.send("104 TURN RIGHT\a\b".encode())
		self.setCoordinates()

		self.socket.send("102 MOVE\a\b".encode())
		self.setCoordinates()
		
		# While avoiding the obstacle, robot can reach it's targer coordinate on the provided axis
		if self.coordinates[axis] == 0:
			return

		self.socket.send("102 MOVE\a\b".encode())
		self.setCoordinates()

		self.socket.send("104 TURN RIGHT\a\b".encode())
		self.setCoordinates()

		self.socket.send("102 MOVE\a\b".encode())
		self.setCoordinates()

		self.socket.send("103 TURN LEFT\a\b".encode())
		self.setCoordinates()

	
	def move(self, axis):
		'''Robot moves until it reaches the target-zero coordinate along the provided axis.'''
		
		while self.coordinates[axis] != 0:
			old = self.coordinates[axis]

			self.socket.send("102 MOVE\a\b".encode())
			self.setCoordinates()

			# If coordinate didn't change -> obstacle is met, avoid it
			if self.coordinates[axis] == old:
				self.collisions += 1
				
				# Collisions limit check
				if self.collisions > COLLISION_LIMIT:
					raise Exception(None)

				self.avoidObstacle(axis)

	
	def navigateToTheTarget(self):
		'''Navigates robot to the (0,0) coordinate.'''
		
		# Decide, whether robot has to go right or left
		if self.coordinates[X] > 0:
			# Go left
			self.rotate(WEST)
		elif self.coordinates[X] < 0:
			# Go right
			self.rotate(EAST)

		# Navigate robot to zero coordinate by the X axis
		self.move(X)

		# Decide, whether robot has to go up or down
		if self.coordinates[Y] > 0:
			# Go down
			self.rotate(SOUTH)
		elif self.coordinates[Y] < 0:
			# Go up
			self.rotate(NORTH)

		# Navigate robot to zero coordinate by the Y axis
		self.move(Y)


	def pickupMessage(self):
		'''Picks and prints the message. Logs out after doing so.'''
		
		self.socket.send("105 GET MESSAGE\a\b".encode())
		self.getResponse(MESSAGE)
		print(self.currentResponse)
		self.socket.send("106 LOGOUT\a\b".encode())


	def start(self):
		'''Orchestrates the whole lifespan of a robot. Also redirects exceptions if any occur.'''
		
		try:
			self.socket.settimeout(NORMAL_TIMEOUT)
			self.authenticate()
			self.getInitialConditions()
			self.navigateToTheTarget()
			self.pickupMessage()
		except Exception as error:
			# No message to redirect
			if error is None:
				pass
			# Exception contains some message -> it needs to be redirected
			else:
				self.socket.send(str(error).encode())
				
		# Timeout exception -> just catch, nothing to resend
		except socket.timeout:
			pass

		# Close the connection socket
		self.socket.close()
        
        

socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socketNumber = 6666

# Find an available socket, starting from 6666, and print socket number to the standard output
while True:
	try:
		socket.bind(("localhost", socketNumber))
		print(f"Started server on port {socketNumber}")
		break
	except:
		socketNumber += 1

# Wait for a connection and operate a robot
socket.listen()
while True:
	connectionSocket, _ = socket.accept()
	robot = Robot(connectionSocket)
	thread = threading.Thread(target=robot.start, args=())
	thread.start()
