Students: 
    Myriam Hazime (myriamh@umich.edu)
    Natalie Kim (nbkim@umich.edu)
Introduction:
    Programming Language Used: Python
    Platform Used: VScode
    Collaborated on GitHub
    
To Run:
1. Open 2 terminals
2. In terminal 1, run "python server.py"
3. In terminal 2, run "python client.py localhost"
4. To log in, type "LOGIN *username* *password*"
5.Run the follwing commands: 
• BALANCE: Checks the currently logged-in user’s USD balance.
• LIST: Retrieves a list of stock records.
~If the user is root, all stock records for all users are displayed.
~If the user is a normal user, only their own stock records are shown.
• BUY <stock_symbol> <amount> <price>: Checks if the user has enough balance, then subtracts the total cost from the user’s balance and adds it stock to their account.
• SELL <stock_symbol> <price> <amount>: Checks if the user owns enough of the stock, then sells it and adds the total value to the user’s balance.
• DEPOSIT <amount>: Adds the specified amount to the logged-in user’s balance.
• LOOKUP <stock_symbol>: Searches for stocks owned by the user that match the given symbol.
• QUIT: Closes the client connection.
• SHUTDOWN: which stops the server completely.This command can only be executed by the root user.

Student Roles:
    Myriam:
        - Implemented commands LIST, LOOKUP, DEPOSIT, SHUTDOWN
        - Integration and debugging
        - Recorded output video
    Natalie:
        - Implemented commands LOGIN, LOGOUT, WHO
        - Integration and debugging
        - Updated database and created README
Bugs in Code:
    - Unable to run using BitVise 
        "Connection failed. FlowSocketConnector: Could not connect to login.umd.umich.edu, port 22. 
        Attempted address: 141.215.69.184. Windows error 10060: A connection attempt failed because
        the connected party did not properly respond after a period of time, or established connection 
        failed because connected host has failed to respond."
    - This error persists when attempting to connect on campus and off-campus using the VPN.
    We also attempted to connect using different computers and accounts. 

       