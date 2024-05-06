# Idena Authetication Discord Bot     

A discord bot that enables you to easily add Idena-Discord account verification.        
You can invite the bot into your server using this link: <placeholder>      

### User commands
 - `/login` verifies a user's address by signing in with Idena      
 - `/update` updates the discord roles of a user in the server where the command is ran     
 - `/logout` removes the discord roles assigned to the user by the bot in all servers that they are in      

### Admin commands
Server administrators may customize role assignment by binding roles to Idena statuses (Newbie, Verified, ...) using `/bindrole` and see the current role bindings using `/getbindings`.        
`/forceupdateall` can be used to update all users from a discord server. Please not that the bot updates all users every day automatically at 15:45 UTC.        
A role without administrator permissions may also be assigned to have access to these commands using `/setbotmanager`.      

NOTE: The autoupdate feature will not work unless all Idena statuses are bound to a role and a bot manager is set.