import hashlib, configparser, asyncio, secrets # Standard libs
import mysql.connector, discord # Requires from pip3: mysql-connector-python, discord-py

### Setup
config = configparser.ConfigParser()
config.read('registration.cfg')

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

# you can find more information regarding the new auth process here: https://github.com/TrinityCore/TrinityCore/issues/25157
#def CalculateSRP6Verifier(username, password, salt):
    #g = int(7)
    #N = int("894B645E89E1535BBDAD5B8B290650530801B18EBFBF5E8FAB3C82872A3E9BB7", 16)
    #userpassupper = f'{username}:{password}'.upper()
    #h1 = hashlib.sha1(userpassupper.encode('utf-8')).digest()
    #h2 = hashlib.sha1(salt + h1)
    #h2 = int.from_bytes(h2.digest(), 'little')
    #verifier = pow(g,h2,N)
    #verifier = verifier.to_bytes(32, 'little')
    #verifier = verifier.ljust(32, b'\x00')
    #return verifier

def GetSRP6RegistrationData(username, password):
    salt = secrets.token_bytes(32)
    verifier = CalculateSRP6Verifier(username, password, salt)
    return [salt, verifier]

#def VerifySRP6Login(username, password, salt, verifier):
    #checkVerifier = CalculateSRP6Verifier(username, password, salt)
    #return verifier == checkVerifier

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
        #password = hashlib.sha1(str.encode(wowUsername + ":" + wowPassword)).hexdigest().upper() # And now make it into a SHA1!
        salt, verifier = GetSRP6RegistrationData(wowUsername, wowPassword) #previous authentication method deprecated on more recent trinity versions. We use more secure auth using salt and verify now.
        
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
        
        registrationSQL = "INSERT INTO account (username,salt,verifier,email,expansion) VALUES(%s, %s, %s, %s, 2)"
        val = (wowUsername, salt, verifier, discordid)
        
        #print(wowPassword)
        cursor.execute(registrationSQL, val)
        connection.commit()
        logString = ("[Register]: User : " + str(message.author) + " has registered successfully with account : " + wowUsername + ".")
        print(logString)
        await send_message(logString, logsChannelID)
        await message.author.send("[Register]: Account has been successfully made.")
        return

client.run(config['discord']['apiKey'])