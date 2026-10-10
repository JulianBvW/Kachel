'''The calculator: what counts, what comes out, what is refused.'''

import math

import harness
from harness import check, section

from kachel import calc


def answer(text):
    result = calc.evaluate(text)
    return result.text if isinstance(result, calc.Answer) else result.message


section('the old basics')
for text, expected in [
        ('2+3*4', '14'), ('(2+3)*4', '20'), ('2^10', '1024'), ('2**3**2', '512'),
        ('3,5*2', '7'), ('1,5+1', '2,5'), ('1.5+1', '2.5'), ('7/2', '3,5'),
        ('-3+1', '-2'), ('  1 + 1 ', '2'), ('0.1+0.2', '0.3'), ('3×4', '12'),
        ('10÷4', '2,5'), ('-(1+2)*2', '-6'), ('2^-1', '0,5')]:
    check(f'{text!r} = {expected}', calc.calculate(text) == expected, calc.calculate(text))

section('functions')
for text, expected in [
        ('sqrt(2)', '1,414213562'), ('√2', '1,414213562'), ('sqrt 2', '1,414213562'),
        ('√(9)+1', '4'), ('sqrt 2 + 1', '2,414213562'),
        ('ln(e)', '1'), ('log(1000)', '3'), ('log2(8)', '3'), ('log(8; 2)', '3'),
        ('exp(0)', '1'), ('abs(-3)', '3'), ('round(2,567; 2)', '2,57'), ('round(2,5)', '3'),
        ('round(-2,5)', '-3'), ('floor(2,7)', '2'), ('ceil(2,1)', '3'),
        ('min(3; 1; 2)', '1'), ('max(3; 1; 2)', '3'), ('LOG(100)', '2')]:
    check(f'{text!r} = {expected}', answer(text) == expected, answer(text))

section('angles')
for text, expected in [
        ('sin(30)', '0,5'), ('sin(180)', '0'), ('cos(90)', '0'), ('tan(45)', '1'),
        ('asin(1)', '90'), ('acos(0)', '90'), ('atan(1)', '45'),
        ('sinr(pi)', '0'), ('cosr(0)', '1'), ('sinr(pi/2)', '1'), ('asinr(1)', '1,570796327'),
        ('rad(180)', '3,141592654'), ('deg(pi)', '180'), ('sin(deg(pi/6))', '0,5')]:
    check(f'{text!r} = {expected}', answer(text) == expected, answer(text))

section('constants, operators, numbers')
for text, expected in [
        ('2*pi', '6,283185307'), ('π', '3,141592654'), ('tau/2', '3,141592654'),
        ('e', '2,718281828'), ('g*2', '19,6133'), ('c/1000', '299792,458'),
        ('17 % 5', '2'), ('5!', '120'), ('3!!', '720'), ('0!', '1'), ('2^3!', '64'),
        ('0xff+1', '256'), ('0b1010*2', '20'), ('1e6/4', '250000'), ('2,5e-3*2', '0,005'),
        ('2^60', '1,152921505e18'), ('1e-7*1', '1e-7'), ('1.5e3+1', '1501')]:
    check(f'{text!r} = {expected}', answer(text) == expected, answer(text))

section('the plain search only takes obvious sums')
for text in ('pi', 'e', 'c', 'g', 'log', '42', '-3', '1e6', '0xff', 'ln(e)',
             '7-Zip', 'g++', 'e2', 'firefox', '', '   ', '2 3', 'abc', '1+', '(1+2'):
    check(f'{text!r} is no sum here', calc.calculate(text) is None, calc.calculate(text))
check('e+1 is one (a digit and an operator)', calc.calculate('e+1') == '3,718281828')
check('sqrt(2) is one', calc.calculate('sqrt(2)') == '1,414213562')

section('problems say what is wrong')
for text, words in [
        ('sqrt(-1)', 'sqrt(-1) geht nicht'), ('(1+2', 'Klammer fehlt'),
        ('foo(2)', 'unbekannt: foo'), ('1/0', 'geteilt durch 0'), ('5 % 0', 'geteilt durch 0'),
        ('tan(90)', 'tan(90) geht nicht'), ('tanr(pi/2)', 'geht nicht'),
        ('171!', 'Fakultät'), ('2,5!', 'Fakultät'), ('2^99999', 'Exponent zu groß'),
        ('10^999', 'Ergebnis zu groß'), ('(-8)^0.5', 'kein reelles Ergebnis'),
        ('log(8; 1)', 'Basis 1'), ('round(1; 2; 3)', 'round braucht 1 bis 2'),
        ('1+', 'unvollständig'), ('2 3', 'Rechenzeichen fehlt'), ('2 # 3', '„#“'),
        ('', 'Rechnung eingeben')]:
    got = answer(text)
    check(f'{text!r}: {words}', words in got, got)

section('review fixes')
for text, expected in [
        ('max(5)', '5'), ('min 3', '3'), ('max(1,2)', '1,2'),
        ('round(1,005; 2)', '1,01'), ('round(2,675; 2)', '2,68'), ('round(-1,005; 2)', '-1,01'),
        ('round(1234; -2)', '1200'),
        ('sin -30', '-0,5'), ('√-4', 'sqrt(-4) geht nicht'), ('sqrt -4', 'sqrt(-4) geht nicht'),
        ('sinr(1e-20)', '1e-20'), ('sin(360)', '0'), ('cos(180)', '-1'), ('sin(-90)', '-1'),
        ('tan(270)', 'tan(270) geht nicht'), ('round(2; 1e9)', 'round: Stellen'),
        ('(' * 2000 + '1' + ')' * 2000, 'zu tief verschachtelt'),
        ('-' * 3000 + '1', 'zu tief verschachtelt')]:
    got = answer(text)
    check(f'{text[:20]!r} -> {expected}', got == expected or expected in got, got)
check('the plain search survives them too',
      calc.calculate('max 2') is None or calc.calculate('max 2') == '2')

section('format_number')
check('whole numbers without decimals', calc.format_number(14.0) == '14')
check('comma by default', calc.format_number(2.5) == '2,5')
check('point on request', calc.format_number(2.5, comma=False) == '2.5')
check('ten significant digits', calc.format_number(1 / 3) == '0,3333333333')
check('minus zero is zero', calc.format_number(-0.0) == '0')
check('huge: with an exponent', calc.format_number(2.0 ** 60) == '1,152921505e18')
check('tiny: with an exponent', calc.format_number(1e-7) == '1e-7')
check('pi to ten digits', calc.format_number(math.pi) == '3,141592654')

harness.report()
