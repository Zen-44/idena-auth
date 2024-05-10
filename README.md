# Idena Authetication Discord Bot     

A discord bot that enables you to easily add Idena-Discord account verification.        
You can invite the bot into your server using this link: https://discord.com/oauth2/authorize?client_id=1235503335595966504&permissions=268453888&scope=applications.commands+bot             

### User commands
 - `/login` verifies a user's address by signing in with Idena      
 - `/update` updates the discord roles of a user in the server where the command is ran     
 - `/logout` removes the discord roles assigned to the user by the bot in all servers that they are in      

### Admin commands
Server administrators may customize role assignment by binding roles to Idena statuses (Newbie, Verified, ...) using `/bindrole` and see the current role bindings using `/getbindings`.        
`/forceupdateall` can be used to update all users from a discord server. Please note that the bot updates all users every day automatically at 15:45 UTC.        
A role without administrator permissions may also be assigned to have access to these commands using `/setbotmanager`.      
Admins may also setup a channel where the bot will post a message with buttons for login, update and logout operations using `/send_interactive_message`. (Send messages and Embed links permissions are necessary if the old invite link was used)       

Don't forget to drag the bot's role above all others that it manages in server settings.       
NOTE: The autoupdate feature will not work unless all Idena statuses are bound to a role and a bot manager is set.