import hashlib, configparser, asyncio # Standard libs
import mysql.connector, discord # Requires from pip3: mysql-connector-python, discord-py

### Setup
config = configparser.ConfigParser()
config.read('registrationconfig')

mysqlHost = config['mysql']['host']
mysqlauthDB = config['mysql']['authdb']
mysqlcharDB = config['mysql']['chardb']
mysqlUser = config['mysql']['user']
mysqlPass = config['mysql']['pass']
mysqlPort = config['mysql']['port']
apiKey = config['discord']['apiKey']
discordServerID = int(config['discord']['targetServer'])
logsChannelID = int(config['discord']['logsChannel'])


client = discord.Client()

@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")

# send_message, arg1 is string, arg2 is output channel
async def send_message(arg1, arg2):
    channel = client.get_channel(arg2)
    await channel.send(arg1)

# sterilize user input so nobody nukes the db
def sterilize(parameter):
    str(parameter)
    parameter = parameter.replace("%;","") # Replace the character ";" with nothing. Does this really need escaping?
    parameter = parameter.replace("`","") # Replace the character "`" with nothing.
    parameter = parameter.replace("(%a)'","%1`") # For any words that end with ', replace the "'" with "`"
    parameter = parameter.replace("(%s)'(%a)","%1;%2") # For any words that have a space, then the character "'" and then letters, replace the "'" with a ";".
    parameter = parameter.replace("'","") # Replace the character "'" with nothing.
    parameter = parameter.replace("(%a)`","%1''") # For any words that end with "`", replace the "`" with "''"
    parameter = parameter.replace("(%s);(%a)","%1''%2") # For any words that have a space, then the character ";" and then letters, replace the ";" with "''".
    return parameter

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    # is message a DM, starts with "register ", and is not bot
    # syntax: register <username> <password>
    if str(message.channel).find("Direct Message") == -1:
        return

    if message.author.bot == True:
        return
    
    if message.content.startswith('register '):
        messageParameters = message.content.split(" ")
        if len(messageParameters) != 3:
            logString = ("[Register]: User : " + str(message.author) + " failed to register with following input : " + messageParameters[0] + " " + messageParameters[1] + " <REDACTED>.")
            print(logString)
            await send_message(logString, logsChannelID)
            await message.author.send("[Register]: There was an error processing your command.\nPlease input `register <username> <password>`.\nExample: `register marco polo` would make a username marco with password polo.")
            return
        
        discordid=str(message.author.id).upper()
        wowUsername = sterilize(messageParameters[1].upper())
        wowPassword = sterilize(messageParameters[2].upper()) # First, set the register query up correctly. All uppercase. USERNAME:PASSWORD
        password = hashlib.sha1(str.encode(wowUsername + ":" + wowPassword)).hexdigest().upper() # And now make it into a SHA1!
        
        # SQL STUFF STARTS HERE
        connection = mysql.connector.connect(user=mysqlUser, password=mysqlPass, host=mysqlHost, database=mysqlauthDB, port=mysqlPort) # db connection
        cursor = connection.cursor() # our cursor that selects n stuff
        registrationSQL = "SELECT username, email FROM account WHERE username = %s OR email = %s" # check if username OR email(discordid) exists
        checkval = (wowUsername, discordid) # this is how we pass multiple variables to the execute script
        cursor.execute(registrationSQL,checkval)
        result = cursor.fetchall()
        connection.commit() # We need this or the script will cache the query.
        if len(result) != 0:
            if result[0][0] == wowUsername: #check if username exists
                logString = ("[Register]: User : " + str(message.author) + " failed to register because that username already exists.")
                print(logString)
                await send_message(logString, logsChannelID)
                await message.author.send("[Register]: An account with that username already exists.")
                return
            elif result[0][1] == discordid: # check if user with discordid exists
                logString = ("[Register]: User : " + str(message.author) + " failed to register because their discordID already exists.")
                print(logString)
                await send_message(logString, logsChannelID)
                await message.author.send("[Register]: An account with your Discord ID already exists.")
                return
        
        registrationSQL = "INSERT INTO account (username,sha_pass_hash,email,expansion) VALUES(%s, %s, %s, 2)"
        val = (wowUsername, password, discordid)
        #print(wowPassword)
        cursor.execute(registrationSQL, val)
        connection.commit()
        logString = ("[Register]: User : " + str(message.author) + " has registered successfully with account : " + wowUsername + ".")
        print(logString)
        await send_message(logString, logsChannelID)
        await message.author.send("[Register]: Account has been successfully made.")
        return

client.run(config['discord']['apiKey'])