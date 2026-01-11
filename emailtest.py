import smtplib

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login("BATYSKURYLYSXXI@gmail.com", "tbup phrp bdnl lthd")
server.sendmail("BATYSKURYLYSXXI@gmail.com", "BATYSKURYLYSXXI@gmail.com", "Test TEST TEST email from smtplib")
server.quit()
