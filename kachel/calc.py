'''The calculator. Pure, so it can be tested, and without eval, ever.

    2+3*4   sqrt(2)   √2   2*pi   sin(30)   17 % 5   5!   0xff+1   1e6/4

A decimal comma and a decimal point both work; the answer uses the comma
unless the question used only points. Arguments are separated by ';',
since the comma is taken: log(8; 2), round(2,567; 2). Angles are in
degrees; sinr, cosr ... take and give radians.

Typed into the plain search, only an obvious sum counts: a digit and an
operation. 'pi' or 'e' alone stay a search for apps. Behind the '=' pill
everything is a calculation, and what does not work says why.
'''

import math
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MAX_EXPONENT = 1000
MAX_FACTORIAL = 170      # 171! no longer fits a float
MAX_ROUND_DIGITS = 15    # more than a float holds anyway

TOKEN = re.compile(r'''
    \s*(?:
      (?P<hex>0[xX][0-9a-fA-F]+)
    | (?P<bin>0[bB][01]+)
    | (?P<dec>(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:[eE][+-]?\d+)?)
    | (?P<name>[A-Za-z]+\d*|π)
    | (?P<op>\*\*|[-+*/^()×÷%!;√])
    )''', re.VERBOSE)


@dataclass
class Answer:
    text: str            # formatted, ready to show and copy
    value: float
    numbers: int = 0     # how many numbers were typed
    operations: int = 0  # operators, functions, factorials


@dataclass
class Problem:
    message: str         # German, says what does not work


class _Fail(Exception):
    pass


# -- the table -------------------------------------------------------------

# Degrees on the axes have exact answers; floating point would give
# sin(180) = 1.2e-16.
EXACT = {'sin': {0: 0.0, 90: 1.0, 180: 0.0, 270: -1.0},
         'cos': {0: 1.0, 90: 0.0, 180: -1.0, 270: 0.0},
         'tan': {0: 0.0, 180: 0.0}}


def _degrees(name, function):
    def apply(x):
        quarter = x % 360
        if name == 'tan' and quarter in (90, 270):
            raise _Fail(f'tan({format_number(x)}) geht nicht')
        if quarter in EXACT[name]:
            return EXACT[name][quarter]
        return function(math.radians(x))
    return apply


def _snap(x, value):
    '''sinr(pi) is 1.2e-16, since pi itself is not exact; it should say
    0. Only noise that small, and only for an angle that is not tiny
    itself -- sinr(1e-20) really is 1e-20.'''
    return 0.0 if abs(value) < 1e-15 and abs(x) > 1e-6 else value


def _tan_radians(x):
    if abs(math.cos(x)) < 1e-12:
        raise _Fail(f'tanr({format_number(x)}) geht nicht')
    return _snap(x, math.tan(x))


def _round(x, digits=0):
    '''Half away from zero, as on paper: round(2,5) = 3, round(1,005; 2)
    = 1,01. Python's round() and binary floats get both wrong, so it goes
    through the decimal the number was written as.'''
    if digits != int(digits) or abs(digits) > MAX_ROUND_DIGITS:
        raise _Fail(f'round: Stellen ganzzahlig von -{MAX_ROUND_DIGITS} '
                    f'bis {MAX_ROUND_DIGITS}')
    step = Decimal(1).scaleb(-int(digits))
    return float(Decimal(repr(x)).quantize(step, rounding=ROUND_HALF_UP))


def _log(x, base=10):
    if base <= 0 or base == 1:
        raise _Fail(f'log zur Basis {format_number(base)} geht nicht')
    return math.log(x, base)


# name -> (function, fewest arguments, most arguments or None for any)
FUNCTIONS = {
    'sqrt': (math.sqrt, 1, 1),
    'ln': (math.log, 1, 1),
    'log': (_log, 1, 2),
    'log2': (math.log2, 1, 1),
    'exp': (math.exp, 1, 1),
    'abs': (abs, 1, 1),
    'round': (_round, 1, 2),
    'floor': (lambda x: float(math.floor(x)), 1, 1),
    'ceil': (lambda x: float(math.ceil(x)), 1, 1),
    'min': (lambda *values: min(values), 1, None),
    'max': (lambda *values: max(values), 1, None),
    'sin': (_degrees('sin', math.sin), 1, 1),
    'cos': (_degrees('cos', math.cos), 1, 1),
    'tan': (_degrees('tan', math.tan), 1, 1),
    'asin': (lambda x: math.degrees(math.asin(x)), 1, 1),
    'acos': (lambda x: math.degrees(math.acos(x)), 1, 1),
    'atan': (lambda x: math.degrees(math.atan(x)), 1, 1),
    'sinr': (lambda x: _snap(x, math.sin(x)), 1, 1),
    'cosr': (lambda x: _snap(x, math.cos(x)), 1, 1),
    'tanr': (_tan_radians, 1, 1),
    'asinr': (math.asin, 1, 1),
    'acosr': (math.acos, 1, 1),
    'atanr': (math.atan, 1, 1),
    'rad': (math.radians, 1, 1),
    'deg': (math.degrees, 1, 1),
}

CONSTANTS = {
    'pi': math.pi, 'π': math.pi, 'tau': math.tau, 'e': math.e,
    'g': 9.80665,          # standard gravity, m/s²
    'c': 299792458.0,      # speed of light, m/s
}


# -- reading ---------------------------------------------------------------

def _tokenize(text):
    '''-> (tokens, separators). A token is ('num', value), ('name', name)
    or ('op', symbol); separators are the decimal marks that were used.'''
    tokens, separators = [], set()
    position = 0
    text = text.strip()
    while position < len(text):
        match = TOKEN.match(text, position)
        if match is None or match.end() == position:
            raise _Fail(f'„{text[position:].strip()[:1]}“ verstehe ich nicht')
        if match['hex']:
            tokens.append(('num', float(int(match['hex'], 16))))
        elif match['bin']:
            tokens.append(('num', float(int(match['bin'][2:], 2))))
        elif match['dec']:
            number = match['dec']
            separators.update(c for c in number if c in ',.')
            tokens.append(('num', float(number.replace(',', '.'))))
        elif match['name']:
            tokens.append(('name', match['name'].lower()))
        else:
            tokens.append(('op', match['op']))
        position = match.end()
        while position < len(text) and text[position].isspace():
            position += 1
    return tokens, separators


class _Parser:
    '''Recursive descent:

        expr    = term  (('+' | '-') term)*
        term    = unary (('*' | '/' | '×' | '÷' | '%') unary)*
        unary   = ('+' | '-') unary | power
        power   = postfix (('^' | '**') unary)?        right-associative
        postfix = atom '!'*
        atom    = number | constant | function '(' args ')'
                | function postfix | '√' postfix | '(' expr ')'
        args    = expr (';' expr)*
    '''

    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.numbers = 0
        self.operations = 0   # '-3' alone is not a calculation

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) \
            else (None, None)

    def take(self):
        token = self.peek()
        self.index += 1
        return token

    def is_op(self, *symbols):
        kind, value = self.peek()
        return kind == 'op' and value in symbols

    def expr(self):
        value = self.term()
        while self.is_op('+', '-'):
            _, op = self.take()
            self.operations += 1
            right = self.term()
            value = value + right if op == '+' else value - right
        return value

    def term(self):
        value = self.unary()
        while self.is_op('*', '/', '×', '÷', '%'):
            _, op = self.take()
            self.operations += 1
            right = self.unary()
            if op in ('*', '×'):
                value = value * right
            elif right == 0:
                raise _Fail('geteilt durch 0')
            elif op == '%':
                value = value % right
            else:
                value = value / right
        return value

    def unary(self):
        if self.is_op('+', '-'):
            _, sign = self.take()
            value = self.unary()
            return -value if sign == '-' else value
        return self.power()

    def power(self):
        base = self.postfix()
        if self.is_op('^', '**'):
            self.take()
            self.operations += 1
            exponent = self.unary()
            if abs(exponent) > MAX_EXPONENT:
                raise _Fail('Exponent zu groß')
            try:
                value = base ** exponent
            except OverflowError:
                raise _Fail('Ergebnis zu groß')
            except ZeroDivisionError:
                raise _Fail('geteilt durch 0')
            # (-8) ** 0.5 is complex in Python.
            if isinstance(value, complex):
                raise _Fail('kein reelles Ergebnis')
            return value
        return base

    def postfix(self):
        value = self.atom()
        while self.is_op('!'):
            self.take()
            self.operations += 1
            if value != int(value) or not 0 <= value <= MAX_FACTORIAL:
                raise _Fail('Fakultät nur für ganze Zahlen von 0 bis '
                            f'{MAX_FACTORIAL}')
            value = float(math.factorial(int(value)))
        return value

    def atom(self):
        kind, value = self.take()
        if kind == 'num':
            self.numbers += 1
            return value
        if kind == 'op' and value == '(':
            inner = self.expr()
            if not self.is_op(')'):
                raise _Fail('Klammer fehlt')
            self.take()
            return inner
        if kind == 'op' and value == '√':
            return self.call('sqrt', [self.operand()])
        if kind == 'name':
            if value in CONSTANTS:
                return CONSTANTS[value]
            if value in FUNCTIONS:
                if self.is_op('('):
                    self.take()
                    args = [self.expr()]
                    while self.is_op(';'):
                        self.take()
                        args.append(self.expr())
                    if not self.is_op(')'):
                        raise _Fail('Klammer fehlt')
                    self.take()
                else:
                    args = [self.operand()]   # sqrt 2, sin -30
                return self.call(value, args)
            raise _Fail(f'unbekannt: {value}')
        if kind is None:
            raise _Fail('unvollständig')
        raise _Fail(f'unerwartet: {value}')

    def operand(self):
        '''What a function takes without brackets: one number, constant
        or bracket with its sign -- 'sqrt 2 + 1' is sqrt(2) + 1.'''
        if self.is_op('+', '-'):
            _, sign = self.take()
            value = self.operand()
            return -value if sign == '-' else value
        return self.postfix()

    def call(self, name, args):
        function, fewest, most = FUNCTIONS[name]
        self.operations += 1
        if len(args) < fewest or (most is not None and len(args) > most):
            wanted = str(fewest) if fewest == most else \
                f'{fewest} bis {most}' if most else f'mindestens {fewest}'
            raise _Fail(f'{name} braucht {wanted} Wert(e), getrennt mit ;')
        try:
            value = function(*args)
        except (ValueError, ZeroDivisionError, ArithmeticError):
            shown = '; '.join(format_number(a) for a in args)
            raise _Fail(f'{name}({shown}) geht nicht')
        except OverflowError:
            raise _Fail('Ergebnis zu groß')
        return float(value)


# -- the answer ------------------------------------------------------------

def format_number(value, comma=True):
    '''Whole numbers without decimals, the rest with up to 10 digits; very
    large and very small ones with an exponent: 1,152921505e18, 1e-7.'''
    if value == 0:
        return '0'      # also for -0.0
    if value == int(value) and abs(value) < 1e15:
        text = str(int(value))
    else:
        text = f'{value:.10g}'
        if 'e' in text:
            mantissa, exponent = text.split('e')
            text = f'{mantissa}e{int(exponent)}'
    return text.replace('.', ',') if comma else text


def evaluate(text):
    '''-> Answer or Problem, for any input. The caller decides whether
    an Answer with no operation in it counts (see calculate).'''
    if not text or not text.strip():
        return Problem('Rechnung eingeben')
    try:
        tokens, separators = _tokenize(text)
        parser = _Parser(tokens)
        value = parser.expr()
        kind, extra = parser.peek()
        if kind is not None:
            raise _Fail('Klammer fehlt' if extra == '(' else
                        f'unerwartet: {extra}' if kind == 'op' else
                        'Rechenzeichen fehlt')
    except _Fail as problem:
        return Problem(str(problem))
    except (OverflowError, ValueError):
        return Problem('Ergebnis zu groß')
    except RecursionError:
        return Problem('zu tief verschachtelt')
    if math.isnan(value) or math.isinf(value):
        return Problem('Ergebnis zu groß')
    comma = separators != {'.'}
    return Answer(format_number(value, comma), value, parser.numbers,
                  parser.operations)


def calculate(text):
    '''The answer as text if `text` is an obvious calculation -- at least
    one number and one operation -- else None. For the plain search,
    where 'pi', 'e' or '42' alone are still words to look for.'''
    answer = evaluate(text)
    if isinstance(answer, Answer) and answer.numbers and answer.operations:
        return answer.text
    return None
