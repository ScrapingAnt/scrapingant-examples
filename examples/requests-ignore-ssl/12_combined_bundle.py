"""verify= and REQUESTS_CA_BUNDLE replace certifi's bundle; to trust your CA *and* the public roots, concatenate them."""
import requests
from _common import URL, PUBLIC, BUNDLE, show
# run.sh built certs/bundle.pem with:  cat "$(python -m certifi)" certs/localhost.pem > certs/bundle.pem
show("requests.get(URL, verify='certs/bundle.pem')", lambda: requests.get(URL, verify=BUNDLE).status_code)
show("requests.get(PUBLIC, verify='certs/bundle.pem')", lambda: requests.get(PUBLIC, verify=BUNDLE).status_code)
