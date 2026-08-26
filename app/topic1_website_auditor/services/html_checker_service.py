import html5lib
from curl_cffi import requests
from pydantic import BaseModel
from typing import List, Optional

class HTMLValidationError(BaseModel):
    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    error_type: str

class HTMLValidationResult(BaseModel):
    url: str
    is_valid: bool
    total_errors: int
    total_warnings: int
    errors: List[HTMLValidationError]
    warnings: List[HTMLValidationError]

def validate_html_content(url: str, html_content: str) -> HTMLValidationResult:
    parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder("dom"))
    parser.parse(html_content)
    
    errors = []
    warnings = []
    
    for err_tuple in parser.errors:
        err_msg = str(err_tuple)
        err_obj = HTMLValidationError(
            line=None,
            column=None,
            message=err_msg,
            error_type="Error"
        )
        errors.append(err_obj)
        
    return HTMLValidationResult(
        url=url,
        is_valid=len(errors) == 0,
        total_errors=len(errors),
        total_warnings=len(warnings),
        errors=errors,
        warnings=warnings
    )

async def fetch_and_validate_html(url: str) -> HTMLValidationResult:
    response = requests.get(url, impersonate="chrome120", timeout=15)
    response.raise_for_status()
    return validate_html_content(url, response.text)
