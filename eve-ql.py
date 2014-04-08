KEY_ID = ""
API_KEY = ""



#colorcodes
GREEN = '\033[92m'
YELLOW ='\033[93m'
RED = '\033[91m'
ENDC = '\033[0m'

# urls
EVE_URL = "https://api.eveonline.com"
STATUS_URL = "/account/AccountStatus.xml.aspx"
CHARACTER_URL = "/account/Characters.xml.aspx"
BALANCE_URL = "/char/AccountBalance.xml.aspx"
WALLETTRANS_URL = "/char/WalletTransactions.xml.aspx"
MARKETORDER_URL = "/char/MarketOrders.xml.aspx"
SKILLQUEUE_URL = "/char/SkillQueue.xml.aspx"


import urllib
import urllib2
import os
from xml.dom import minidom
import datetime
from decimal import *
import locale
locale.setlocale(locale.LC_ALL, 'en_EN.UTF-8')
import sqlite3
ORDERSTATE_DICT = {0:"open", 1:"closed", 2:"expired", 3:"cancelled", 4:"pending", 5:"character delted"}

conn = sqlite3.connect("eve.db")

class Status:
    def __init__(self,time, paiduntil, logonminutes):
        self.time = time
        self.paiduntil = paiduntil
#        self.createdate = createdate
#        self.logoncount = logoncount
        self.logonminutes = logonminutes
        
    def __str__(self):
        return "Time: %s Paid Until: %s Logon Time: %s" % (self.time, self.paiduntil, self.logonminutes)

class Transaction:
    def __init__(self, time, name, price, quantity, sell):
        self.time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
        self.name = name
        self.price = Decimal(price)
        self.quantity = int(quantity)
        self.sell = ( True if sell=="sell" else False)
    
    def __str__(self):
        string = "Time: %s Name: %s Price: "% (self.time, self.name)
        if self.sell:
            string += GREEN
        else:
            string += RED + "-"
        string += locale.format('%.2f', self.price * self.quantity, grouping=True) + ENDC
        return string

class MarketOrder:
    def __init__(self, volRemaining, orderState, duration, price, issued, typeID):
        self.volRemaining = int(volRemaining)
        self.orderState = int(orderState)
        self.duration = int(duration)
        self.price = Decimal(price)
        self.issued = datetime.datetime.strptime(issued, "%Y-%m-%d %H:%M:%S")
        self.typeID = typeID
        self.expires = self.issued + datetime.timedelta(days=self.duration)
        self.name = ""

    def __str__(self):
        string = "Item: %s, Price: " % self.name + GREEN + locale.format('%.2f', self.price, grouping=True)\
        + ENDC + " Vol: " + str(self.volRemaining) + " Exp: " + RED + str(self.expires) + ENDC
        return string

class Skill:
    def __init__(self, typeID, level, startTime, endTime, eveTime):
        self.typeID = typeID
        self.level = int(level)
        self.startTime = datetime.datetime.strptime(startTime, "%Y-%m-%d %H:%M:%S") if startTime!='' else ''
        self.endTime = datetime.datetime.strptime(endTime, "%Y-%m-%d %H:%M:%S") if endTime!='' else ''
        self.name = ""
        self.eveTime = eveTime

    def until(self):
        # today = datetime.datetime.now()
        if self.startTime=='' or self.endTime=='':
            raise Error('No Skills are training!')
        today = self.eveTime
        if self.endTime > today:
            rawDifference = self.endTime - today
            difference = datetime.timedelta(days = rawDifference.days, seconds = rawDifference.seconds)
            return str(difference)
        else:
            return "Done"
        
    def __str__(self):
        string = "Name: %s, Level: %s, End: %s " % (self.name, self.level, self.endTime) + GREEN + "Done in: "\
            + self.until() + ENDC
        return string



def getXML(url):
    params = urllib.urlencode({'keyID': KEY_ID, 'vCode': API_KEY})
    data = urllib2.urlopen(EVE_URL + url, params)
    xmldoc = minidom.parse(data)
    return xmldoc
    

def getCharacterXML(url,charid):
    params = urllib.urlencode({'keyID': KEY_ID, 'vCode': API_KEY, 'characterID': charid})
    data = urllib2.urlopen(EVE_URL + url, params)
    xmldoc = minidom.parse(data)
    return xmldoc

def getStatus():
    xmldoc = getXML(STATUS_URL)
    time = xmldoc.getElementsByTagName('currentTime')[0].childNodes[0].nodeValue
    paiduntil = xmldoc.getElementsByTagName('paidUntil')[0].childNodes[0].nodeValue
    logontime = xmldoc.getElementsByTagName('logonMinutes')[0].childNodes[0].nodeValue

    realtime = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
    realpaiduntil = datetime.datetime.strptime(paiduntil, "%Y-%m-%d %H:%M:%S")

    st = Status(realtime, realpaiduntil, datetime.timedelta(minutes=int(logontime)))
    return st

def getChar():
    xmldoc = getXML(CHARACTER_URL)
    char = xmldoc.getElementsByTagName('row')[0].getAttributeNode('characterID').nodeValue
    return char


def getBalance(charid):
    xmldoc = getCharacterXML(BALANCE_URL, charid)
    balance = Decimal(xmldoc.getElementsByTagName('row')[0].getAttributeNode('balance').nodeValue)
    return balance

def getWalletTransactions(charid):
    xmldoc = getCharacterXML(WALLETTRANS_URL, charid)
    transactions = xmldoc.getElementsByTagName('row')
    transclass = [ Transaction(x.getAttributeNode('transactionDateTime').nodeValue, 
                               x.getAttributeNode('typeName').nodeValue,
                               x.getAttributeNode('price').nodeValue,
                               x.getAttributeNode('quantity').nodeValue,
                               x.getAttributeNode('transactionType').nodeValue)
                   for x in transactions]  
    return transclass

def getMarketOrders(charid):
    xmldoc = getCharacterXML(MARKETORDER_URL, charid)
    orders = xmldoc.getElementsByTagName('row')
    ordersclass = [ MarketOrder(x.getAttributeNode('volRemaining').nodeValue,
                                x.getAttributeNode('orderState').nodeValue,
                                x.getAttributeNode('duration').nodeValue,
                                x.getAttributeNode('price').nodeValue,
                                x.getAttributeNode('issued').nodeValue,
                                x.getAttributeNode('typeID').nodeValue)
                    for x in orders]
    for order in ordersclass:
        result = conn.execute('SELECT typeName from invtypes where typeID=%s' % order.typeID).fetchall()[0][0]
        order.name = result
    return ordersclass

def getSkillQueue(charid, status):
    xmldoc = getCharacterXML(SKILLQUEUE_URL, charid)
    skills = xmldoc.getElementsByTagName('row')
    skillsclass = [ Skill(x.getAttributeNode('typeID').nodeValue,
                          x.getAttributeNode('level').nodeValue,
                          x.getAttributeNode('startTime').nodeValue,
                          x.getAttributeNode('endTime').nodeValue,
                          status.time)
                    for x in skills]
    
    for skill in skillsclass:
        result = conn.execute('SELECT skillName from skills_master where typeID=%s' % skill.typeID).fetchall()[0][0]
        skill.name = result
    return skillsclass

def stats():
    status = getStatus()
    print("Server time: %s" % status.time)
    print("Paid Until: %s" % status.paiduntil)
    print("Logged time: %s" % status.logonminutes)

    charid = getChar()
    balance = getBalance(charid)
    print("Wallet: " + GREEN + locale.format('%.2f', balance, grouping=True) + ENDC)

    print("---------------------------------" + YELLOW + "TRANSACTIONS" + ENDC +"---------------------------------------")
    transactions = getWalletTransactions(charid)
    filterdate = datetime.datetime.today() - datetime.timedelta(days=1)
    transactionsfiltered = [x for x in transactions if x.time >= filterdate]
    transsum = 0
    for x in transactionsfiltered:
        transsum += x.price * x.quantity
        print(x)
    print("Sum: " + GREEN + locale.format('%.2f', transsum, grouping=True) + ENDC)

    print("----------------------------------" + YELLOW + "MARKET" + ENDC +"--------------------------------------------")
    orders = getMarketOrders(charid)
    ordersfiltered = [x for x in orders if x.orderState==0]
    for x in ordersfiltered:
       print(x)
    orderssum = sum([x.price * x.volRemaining for x in ordersfiltered])
    print("Orderssum: " + GREEN + locale.format('%.2f', orderssum, grouping=True) + ENDC)
    

    print("------------------------------------" + YELLOW + "SKILLS" + ENDC + "-------------------------------------------")
    skills = getSkillQueue(charid, status)
    for x in skills:
        print(x)


if __name__ == "__main__":
    import evetool
    stats()

    
