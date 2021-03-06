import json
import os
import random
import re
import time

from locust import TaskSet, task

from .utils import parse_params_from_location
from .questionnaire_mixins import QuestionnaireMixins
from .token_generator import create_token

r = random.Random()

from pprint import pprint
import urllib.parse

class SurveyRunnerTaskSet(TaskSet, QuestionnaireMixins):
    def __init__(self, parent):
        super().__init__(parent)

        self.base_url = self.client.base_url
        self.redirect_params = {}

        requests_filepath = os.environ.get('REQUESTS_JSON', 'requests.json')

        with open(requests_filepath, encoding='utf-8') as requests_file:
            requests_json = json.load(requests_file)
            self.requests = requests_json['requests']
            self.eq_id = requests_json['eq_id']
            self.form_type = requests_json['form_type']

    @task
    def start(self):
        self.do_launch_survey()
        self.replay_requests()

    def replay_requests(self):
        user_wait_time_min = int(os.getenv('USER_WAIT_TIME_MIN_SECONDS', 1))
        user_wait_time_max = int(os.getenv('USER_WAIT_TIME_MAX_SECONDS', 2))
        url_name_regex = r'{.*?}'

        # self.get('/questionnaire', expect_redirect=True)

        for request in self.requests:
            url_name = re.sub(url_name_regex, '{id}', request['url'])
            request_url = request['url'].format_map(self.redirect_params)

            if request['method'] == 'GET':
                expect_redirect = "redirect_route" in request
                response = self.get(
                    request_url, name=url_name, expect_redirect=expect_redirect
                )

                if expect_redirect:
                    self.handle_redirect(request, response)

                if user_wait_time_min and user_wait_time_max:
                    time.sleep(r.randint(user_wait_time_min, user_wait_time_max))

            elif request['method'] == 'POST':
                response = self.post(
                    self.base_url, request_url, request['data'], name=url_name
                )
                if "redirect_route" in request:
                    self.handle_redirect(request, response)

            else:
                raise Exception(
                    f"Invalid request method {request['method']} for request to: {request_url}"
                )

    def handle_redirect(self, request, response):
        self.redirect_params.update(
            parse_params_from_location(
                response.headers['Location'], request['redirect_route']
            )
        )

    def do_launch_survey(self):
        token = create_token(eq_id=self.eq_id, form_type=self.form_type)

        url = f'/session?token={token}'
        self.get(url=url, name='/session', expect_redirect=True)
