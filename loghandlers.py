from zope.interface import implementer, implements
from twisted.logger import ILogObserver
from twisted.logger import LogLevel
import json
import urllib

from twisted.logger import Logger
log = Logger()
import settings

from twisted.web.iweb import IBodyProducer
from twisted.internet import defer
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet import reactor
from twisted.internet import protocol
from zope.interface import implementer

from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer

# The below value comes up whenever a mailgun API requested is attempted
# And the intended recipient of the mail is an incorrectly entered/obviously wrong
# email address. eg `asd@x.xa`
text_for_failed_email_address_entered = "A mailgun error occurred: <class 'requests.exceptions.HTTPError'> - 400 Client Error: BAD REQUEST for url: https://api.mailgun.net/v3/canarytokens.org/messages"

@implementer(IBodyProducer)
class BytesProducer:
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass



@implementer(ILogObserver)
class errorsToWebhookLogObserver(object):
    """
    Log observer that sends errors out to a Slack endpoint.
    """
    def __init__(self, formatEvent):
        """
        @param formatEvent: A callable that formats an event.
        @type formatEvent: L{callable} that takes an C{event} argument and
            returns a formatted event as L{unicode}.
        """
        self.formatEvent = formatEvent


    def __call__(self, event):
        """
        Check if log_level Error or higher, if so post to webhook

        @param event: An event.
        @type event: L{dict}
        """
        if event['log_level'] == LogLevel.error or event['log_level'] == LogLevel.critical:
            if event['log_namespace'] == "log_legacy":
                # A log from the legacy logger has been called, therefore use a different key to get the log message
                postdata = {'text':event['log_text']}
            else:
                postdata = {'text':event['log_format']}
            if postdata['text'] == 'Unhandled error in Deferred:' or postdata['text'] == text_for_failed_email_address_entered:
                # filters out non useful spam of messages seen before with these exact contents
                return
            d = httpRequest(postdata)

def httpRequest(postdata):
    agent = Agent(reactor)
    headers={'Content-Type': ['application/x-www-form-urlencoded']}
    data_str = json.dumps(postdata)
    body = BytesProducer(data_str)
    url = settings.ERROR_LOG_WEBHOOK
    d = agent.request("POST", url, Headers(headers), body)

    def handle_response(response):
        if response.code == 200:
            d = defer.succeed('')
        else:
            log.warn('Failed to post to webhook')
            d = None
        return d

    d.addCallback(handle_response)
    return d

def webhookLogObserver(recordSeparator=u"\x1e"):
    """
    Create a L{errorsToWebhookLogObserver} that emits error and critical
    loglines' text to a specified webhook URL by doing a HTTP POST.

    @param recordSeparator: The record separator to use.
    @type recordSeparator: L{unicode}

    @return: A log observer that POST critical and Error logs to a webhook.
    @rtype: L{errorsToWebhookLogObserver}

    """
    return errorsToWebhookLogObserver(
        lambda event: u"{0}{1}\n".format(recordSeparator, eventAsJSON(event))
    )