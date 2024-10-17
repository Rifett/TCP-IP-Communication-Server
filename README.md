# TCP/IP Communication Server

## Overview
This project involves developing a multithreaded TCP/IP server for controlling remote robots. 
Robots connect to the server, authenticate, and navigate towards the target coordinates [0,0] on a 2D space plane. 
The server sends movement instructions and handles communication using a custom text-based protocol. 
The goal is to direct the robots to retrieve a secret message located at coordinates [0,0].

## Features
- **Multithreaded design**: The server can handle multiple robot clients simultaneously.
- **Text-based protocol**: Communication is done via a custom text protocol.
- **Authentication**: Robots authenticate using username and a set of predefined key pairs.
- **Robot navigation**: The server directs robots towards the origin [0,0] using basic movement commands, which are MOVE and TURN.
- **Error handling**: Server anylyzes and sends proper responses to syntax and logic errors.
- **Robot recharging**: Robots notify the server when they need to recharge and resume their walk to the zero-coordinate after a timeout.

## Communication Protocol
The server and robots communicate using a simple textual protocol, with each message ending by the `\a\b` combination. 
The server responds to robot commands and vice versa using predefined messages format.

### Server Messages:
- `SERVER_CONFIRMATION`: Sends a confirmation code.
- `SERVER_MOVE`: Commands the robot to move forward.
- `SERVER_TURN_LEFT`: Commands the robot to turn left.
- `SERVER_TURN_RIGHT`: Commands the robot to turn right.
- `SERVER_PICK_UP`: Instructs the robot to pick up the secret message.
- `SERVER_LOGOUT`: Informs the robot to terminate the connection after success.
- `SERVER_KEY_REQUEST`: Requests the Key ID for authentication.
- `SERVER_OK`: Sends a positive acknowledgment.
- `SERVER_LOGIN_FAILED`: Notifies that authentication failed.
- `SERVER_SYNTAX_ERROR`: Informs about a syntax error.
- `SERVER_LOGIC_ERROR`: Informs about a logic error.
- `SERVER_KEY_OUT_OF_RANGE_ERROR`: Notifies that the provided Key ID is invalid.

### Client Messages
- `CLIENT_USERNAME`: Sends the robot’s username for authentication.
- `CLIENT_KEY_ID`: Sends the Key ID for authentication.
- `CLIENT_CONFIRMATION`: Confirms the robot's authentication code.
- `CLIENT_OK`: Sends the robot’s coordinates after a movement.
- `CLIENT_RECHARGING`: Notifies the server that the robot is recharging.
- `CLIENT_FULL_POWER`: Notifies the server that the robot is fully recharged.
- `CLIENT_MESSAGE`:Sends the discovered secret message.

## Error Handling
- **Syntax errors**: If a client sends a message with incorrect syntax or exceeding the maximum message length, the server will send `SERVER_SYNTAX_ERROR` and terminate the connection.
- **Logic errors**: Incorrect message flow, such as sending recharging status without starting the recharge, results in a `SERVER_LOGIC_ERROR`.
- **Key out-of-range**: If a client provides an invalid Key ID, the server responds with `SERVER_KEY_OUT_OF_RANGE_ERROR`.

## Special Situations
- **Segmentation of a messages**: Messages can arrive in parts due to network delays. The server is optimized to handle segmented messages.
- **Simultaneous arrival of messages**: The server processes multiple messages arriving together in the buffer, ensuring correct sequence handling.

## Server Optimization
To ensure server's efficiency, the following optimizations have been implemented:
- **Early error detection**: The server detects message errors as soon as possible.
For instance, if the server receives a partial message that already exceeds the maximum allowed length (e.g., a username longer than 20 characters), it immediately responds with `SERVER_SYNTAX_ERROR` without waiting for the rest of the message to arrive.
This reduces unnecessary processing.
- **Timeout mechanisms**: Timeout mechanisms ensure that the server does not wait indefinitely for a response.
For example, if a robot does not respond within a predefined timeout (`NORMAL_TIMEOUT` or `RECHARGING_TIMEOUT`), the server closes the connection, freeing up resources for other clients.



