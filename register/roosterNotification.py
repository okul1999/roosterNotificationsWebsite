import urllib2, re
from datetime import datetime, timedelta
from pushbullet.pushbullet import PushBullet
from operator import itemgetter
import sqlite3

conn = sqlite3.connect('../db.sqlite3')
cur = conn.cursor()
cur_update = conn.cursor()

with open('/etc/api_key.txt') as f:
    key = f.read().strip()
pb = PushBullet(key)

for user in cur.execute('SELECT * FROM register_user'):
    print user
    student = bool(user[3])
    email = user[7]
    if student:
        iden = user[2]
        class_code = user[6]
        if int(class_code[0]) <= 2:
            url = "http://gepro.nl/roosters/rooster.php?klassen%5B%5D=y" + str(class_code) + "&type=Klasrooster&wijzigingen=1&school=1814"
        else:
            url = "http://gepro.nl/roosters/rooster.php?leerling=" + str(
                iden) + "&type=Leerlingrooster&afdeling=y" + str(class_code) + "&wijzigingen=1&school=1814&tabblad=1"
    else:
        iden = user[4]
        url = "http://gepro.nl/roosters/rooster.php?docenten%5B%5D=" + str(
            iden) + "&type=Docentrooster&wijzigingen=1&school=1814"
    htmlPage = urllib2.urlopen(url).read()

    lastChangedPat = re.compile('([0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9] [0-9]+:[0-9][0-9]:[0-9][0-9])')
    dateStr = re.search(lastChangedPat, htmlPage).group()
    date = datetime.strptime(dateStr, "%d-%m-%Y %H:%M:%S")
    db_date = datetime.strptime(str(user[1]), "%Y-%m-%d %H:%M:%S.%f")
    if date - db_date < timedelta():
        print "nothing new for " + str(iden)
        continue

    if student:
        cur_update.execute("UPDATE register_user SET updated=? WHERE number=? AND email=?", (str(datetime.now()), iden, email))
    else:
        cur_update.execute("UPDATE register_user SET updated=? WHERE teacher=? AND email=?", (str(datetime.now()), iden, email))

    pb_users = [i for i in pb.contacts if (i.name == str(iden) and i.email == str(email))]
    for pb_user in pb_users:
        parts = []
        stage = 0
        changePat = re.compile('class="tableCell(New|Removed)">(y([0-9]*[a-z]*)|[a-z]+|\?)')
        hourPat = re.compile('class="tableHeader">([0-9])e uur')
        dayPat = re.compile('<td align="left" width="auto" class="tableCell">')

        for change in re.finditer(changePat, htmlPage):
            if change.group(1) == "Removed":
                parts.append([change.group(2)])
                for tempHour in re.finditer(hourPat, htmlPage[:change.start()]):
                    hour = tempHour
                parts[-1].append(hour.group(1))
                day = re.findall(dayPat, htmlPage[hour.end():change.start()])
                parts[-1].append(len(day))
            else:
                stage += 1
                if stage == 1:
                    parts.append([change.group(2)])
                else:
                    parts[-1].append(change.group(2))
                if stage == 3:
                    stage = 0
                    for tempHour in re.finditer(hourPat, htmlPage[:change.start()]):
                        hour = tempHour
                    parts[-1].append(hour.group(1))
                    day = re.findall(dayPat, htmlPage[hour.end():change.start()])
                    parts[-1].append(len(day))

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        text = ""
        parts = sorted(parts, key=itemgetter(-1))
        for part in parts:
            text += str(days[part[-1]-1]) + " " + part[-2] + ("st " if part[-2] == "1" else ("nd " if part[-2] == "2" else "th ")) + "hour "
            if len(part) == 5:
                text += part[0] + " " + part[1] + " " + part[2] + "\n"
            else:
                text += part[0] + "\n"
        if text == "":
            text = "No changes in timetable."

        if user[5] == text:
            print "time changed, no update"
        else:
            if student:
                cur_update.execute("UPDATE register_user SET lastText=? WHERE number=? AND email=?", (text, iden, email))
            else:
                cur_update.execute("UPDATE register_user SET lastText=? WHERE teacher=? AND email=?", (text, iden, email))

            cur_update.execute("SELECT Count(*) FROM register_user")
            text  += "\nHelp us grow.\nNow %s users, tell your friends" % cur_update.fetchone()[0]
            print text
            success, push = pb_user.push_note("lesuitval.info", text)

conn.commit()
conn.close()
