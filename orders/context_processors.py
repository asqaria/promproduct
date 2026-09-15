from orders.forms import QuoteForm


def quote_form(request) -> dict:
    return {"quote_form": QuoteForm()}
