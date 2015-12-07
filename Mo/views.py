# -*- coding: utf-8 -*-
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import smart_str
from Mo.models import mo_weixin_config as weixin_config
from Mo.models import mo_ak_ttl as ak_ttl
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import xml.etree.ElementTree as ET
import urllib2,hashlib,json,time


TOKEN = ""
APPKEY = ''
APPSEC = ''
ACCTOK = ''
ACCTIM = 0
ACCTTL = 0

TEMPID = ''

@csrf_exempt
def handleRequest(request):
    print request
    print request.method

    loadWeixinConfig()
    print 'App_ID:'+APPKEY+'\nAPPSEC:'+APPSEC
    checkAccessToken()
    print 'Token:'+ACCTOK+'\nTime:'+str(ACCTIM)+'\nTTL:'+str(ACCTTL)

    if request.method == 'GET':
        response = HttpResponse(checkSignature(request), content_type="text/plain")
        return response
    elif request.method == 'POST':
        response = HttpResponse(responseMsg(request), content_type="application/xml")
        return response
    else:
        return None


def loadWeixinConfig():
    for items in weixin_config.objects.all():
        global TOKEN, APPKEY, APPSEC
        TOKEN =  items.token
        APPKEY = items.app_id
        APPSEC = items.app_secret

def checkAccessToken():
    global ACCTOK,ACCTIM,ACCTTL
    for items in ak_ttl.objects.filter(app_id = APPKEY):
        ACCTOK = items.access_token
        ACCTIM = items.get_time
        ACCTTL = items.expires_in

    if APPKEY !=''and APPSEC !='':
        if time.time() - ACCTIM > ACCTTL:
            getAccessToken()

def method_get_api(url):
    response = urllib2.urlopen(url).read()
    dict_data = json.loads(response)
    return dict_data

def getAccessToken():
    print 'getAccessToken'
    global APPKEY,APPSEC,ACCTIM,ACCTOK,ACCTTL
    url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid='+APPKEY+'&secret='+APPSEC
    dict_data = method_get_api(url)
    token = dict_data.get('access_token')
    expires_in = dict_data.get('expires_in')
    if token and expires_in:
        ACCTIM = time.time()
        ACCTTL = expires_in-60
        ACCTOK = token
    data = ak_ttl.objects.filter(app_id = APPKEY)
    data.delete()
    data = ak_ttl.objects.create(app_id = APPKEY,expires_in = ACCTTL,access_token = ACCTOK,get_time = ACCTIM)
    data.save()

def checkSignature(request):
    global TOKEN
    signature = request.GET.get("signature", None)
    timestamp = request.GET.get("timestamp", None)
    nonce = request.GET.get("nonce", None)
    echoStr = request.GET.get("echostr",None)

    token = TOKEN
    print token
    tmpList = [token,timestamp,nonce]
    tmpList.sort()
    tmpstr = "%s%s%s" % tuple(tmpList)
    tmpstr = hashlib.sha1(tmpstr).hexdigest()
    if tmpstr == signature:
        checkAccessToken()
        return echoStr
    else:
        return None

def responseMsg(request):
    rawStr = request.body
    msg = paraseMsgXml(ET.fromstring(rawStr))
    msgtype = msg.get('MsgType','')
    print msgtype
    if msgtype == 'text':
        replyContent = '请稍等~'#msg.get('Content','?')
        return getReplyTextXml(msg,replyContent)
    elif msgtype =='event':
        event = msg.get('Event','')
        print event
        if event == 'subscribe':
            replyContent = '感谢关注！'
            uid = msg.get('FromUserName','')
            print uid
            sendCustomTuwenJson(uid)
            return None#getReplyTextXml(msg,replyContent)
        elif event == 'merchant_order':
           OrderID =  msg.get('OrderId','')
           getOrderInfo(OrderID)
        elif event == 'CLICK':
            replyContent = '暂未上线，敬请期待！'
            return getReplyTextXml(msg,replyContent)
        else:
            return None

    else:
        return None

def paraseMsgXml(rootElem):
    msg = {}
    if rootElem.tag == 'xml':
        for child in rootElem:
            msg[child.tag] = smart_str(child.text)
    return msg


def getReplyTextXml(msg,replyContent):
    extTpl = "<xml><ToUserName><![CDATA[%s]]></ToUserName><FromUserName><![CDATA[%s]]></FromUserName><CreateTime>%s</CreateTime><MsgType><![CDATA[%s]]></MsgType><Content><![CDATA[%s]]></Content><FuncFlag>0</FuncFlag></xml>";
    extTpl = extTpl % (msg['FromUserName'],msg['ToUserName'],str(int(time.time())),'text',replyContent)
    return extTpl

def sendCustomTextJson(UserID,Message):
    url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token='+ACCTOK
    values = {
        "touser":UserID,
        "msgtype":"text",
        "text":
            {
                "content":Message
            }
    }
    data = json.dumps(values,ensure_ascii=False)
    print data
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)
    the_page = response.read()
    print the_page

def sendCustomTuwenJson(UserID):
    url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token='+ACCTOK
    values = {
        "touser":UserID,
        "msgtype":"news",
        "news":{
            "articles":[
                {
                    "title":"门票上线啦！预订即送大礼！",
                    "description":"",
                    "url":"",
                    "picurl":""
                }
            ]
        }
    }
    data = json.dumps(values,ensure_ascii=False).encode('utf-8')
    print data
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)
    the_page = response.read()
    print the_page

def getOrderInfo(OrderID):
    url = "https://api.weixin.qq.com/merchant/order/getbyid?access_token="+ACCTOK
    values = {
         "order_id": OrderID
    }
    data = json.dumps(values,ensure_ascii=False)
    print data
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)
    OrderInfo = response.read()
    sendOrderInfo(OrderInfo)

def sendOrderInfo(OrderInfo):
    info = json.loads(OrderInfo)
    print type(info)
    print info
    orderid = info['order']['order_id']
    buyer_openid = info['order']['buyer_openid']
    receiver_name = info['order']['receiver_name']
    receiver_mobile = info['order']['receiver_mobile']
    tmp = float(info['order']['order_total_price'])
    tmp = ("%.2f" % (tmp/100))
    order_total_price =str(tmp)
    tmp = info['order']['order_status']
    order_status = ''
    if tmp==2:
        order_status = '待发货'
    elif tmp == 3:
        order_status = '已发货'
    elif tmp == 5:
        order_status = '已完成'
    elif tmp == 8:
        order_status = '维权中'
    else:
        order_status = "未知"
    product_name = info['order']['product_name']
    product_sku = info['order']['product_sku']
    skulist = str(product_sku).split('$')
    event_time = product_sku
    for item in skulist:
        event_time = item

    url = 'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token='+ACCTOK
    values = {
        "touser":buyer_openid,
        "template_id":TEMPID,
        "url":"",
        "topcolor":"#FF0000",
        "data":{
                "first": {
                    "value":"恭喜您购买成功！",
                    "color":"#173177"
                },
                "keyword1":{
                    "value":'', #活动名称
                    "color":"#173177"
                },
                "keyword2": {
                    "value":product_name,#门票名称
                    "color":"#173177"
                },
                "keyword3": {
                    "value":'',#活动地点
                    "color":"#173177"
                },
                "keyword4": {
                    "value":event_time,#活动时间
                    "color":"#173177"
                },
                "keyword5": {
                    "value":receiver_name,#姓名
                    "color":"#173177"
                },
                "remark":{
                    "value":"如有疑问可发送#姓名+咨询内容#至本微信公众号咨询，我们将在8小时内为您解答。",
                    "color":"#173177"
                }
        }
    }
    data = json.dumps(values,ensure_ascii=False)
    print data
    req = urllib2.Request(url, data.encode('utf-8'))
    response = urllib2.urlopen(req)
    the_page = response.read()
    print the_page

