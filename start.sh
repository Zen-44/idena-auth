# script to get the bot up and running

pkill gunicorn
screen -X -S bot quit
screen -X -S site quit

cd idena-auth
screen -dmS bot python3.11 bot.py
screen -dmS site gunicorn -b :443 --certfile=/root/idena-auth/certs/discord-bot.idena.cloud.crt --keyfile=/root/idena-auth/certs/discord-bot.idena.cloud.key auth:app
cd

# crontab for reboots
# (crontab -l 2>/dev/null; echo "@reboot bash $PWD/idena-auth/start.sh") | crontab -
# magic symbol remover
# sed -i 's/\r$//' idena-auth/start.sh
