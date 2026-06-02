import ssl

import certifi
from django.core.mail.backends.smtp import EmailBackend


class CertifiSMTPEmailBackend(EmailBackend):
    """
    SMTP backend that uses certifi CA bundle for TLS verification.
    Useful on local Python installs missing system CA chain.
    """

    @property
    def ssl_context(self):
        if self.ssl_certfile or self.ssl_keyfile:
            ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
            return ssl_context
        return ssl.create_default_context(cafile=certifi.where())
