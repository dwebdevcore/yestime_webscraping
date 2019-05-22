import unittest
from dha_poc.start import flask_app
from dha_poc.api.controllers import *


class StandardTest(unittest.TestCase):

    def setUp(self):
        flask_app.testing = True

    def tearDown(self):
        pass # do nothing