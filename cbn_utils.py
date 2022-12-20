def check_arg_type(name='', value=None, value_type=None) -> bool:
    assert type(value) == value_type, f'"{name}" argument must be of type {value_type.__name__}, NOT {type(value).__name__}'


def check_string_arg(name='', value='', allowed_values=[], disallowed_values=[]) -> bool:
    passes, message = True, ''
    if len(allowed_values):
        if value not in allowed_values:
            passes = False
            message = f'"{name}" argument must be a str from the following list: {allowed_values}. "{value}" was provided. '
    if len(disallowed_values):
        if value in disallowed_values:
            passes = False
            message += f'"{name}" argument must be a str NOT from the following list: {disallowed_values}. "{value}" was provided. '
    assert passes, message


def check_list_arg(name='', values=[], allowed_values=[], disallowed_values=[]) -> bool:
    passes, message = True, ''
    for value in values:
        if len(allowed_values):
            if value not in allowed_values:
                passes = False
                message += f'"{name}" argument must be from the following list: {allowed_values}. "{value}" was provided. '
        if len(disallowed_values):
            if value in disallowed_values:
                passes = False
                message += f'"{name}" argument must NOT be from the following list: {disallowed_values}. "{value}" was provided. '
    assert passes, message


def strikethrough(x) -> str:
    result = ''
    for character in str(x):
        result += (character + '\u0336')
    return result