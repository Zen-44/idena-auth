# script to get the bot up and running

pkill gunicorn
screen -X -S bot quit
screen -X -S site quit

cd discord-bot
screen -dmS bot python3.11 bot.py
screen -dmS site gunicorn -b :443 --certfile=/root/discord-bot/certs/idena.cloud.crt --keyfile=/root/discord-bot/certs/idena.cloud.key auth:app
cd

# crontab for reboots
# (crontab -l 2>/dev/null; echo "@reboot bash $PWD/discord-bot/start.sh") | crontab -
