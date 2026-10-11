from copy import deepcopy
from contract import TRUTH, score

candidate = deepcopy(TRUTH["links"])
print(score("links", candidate)["accepted_page"])
candidate[0]["buy_url"] = "https://catalog.example/buy/wrong"
print(score("links", candidate)["accepted_page"])
