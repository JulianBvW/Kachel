'''The argument list that runs a command in a terminal.'''

import harness
from harness import check, section

from kachel import launch

KEEP = '\nexec "${SHELL:-sh}"'

section('terminal_argv')
argv = launch.terminal_argv('ghostty --working-directory=.', '-e', 'ssh home-server')
check('ghostty as set on this machine',
      argv == ['ghostty', '--working-directory=.', '-e', 'sh', '-c',
               'ssh home-server' + KEEP], argv)
argv = launch.terminal_argv('gnome-terminal', '--', 'htop')
check('gnome-terminal with --', argv[:3] == ['gnome-terminal', '--', 'sh'], argv)
argv = launch.terminal_argv('kitty', '', 'htop')
check('no exec argument at all', argv[:2] == ['kitty', 'sh'], argv)

command = 'cd ~/Projekte/my-app ; claude --resume "a b" && echo \'x\''
argv = launch.terminal_argv('ghostty', '-e', command)
check('the command arrives as one argument, quotes, ; and ~ untouched',
      argv[-1] == command + KEEP and argv[-2] == '-c', argv)
check('a shell takes over afterwards', argv[-1].endswith('exec "${SHELL:-sh}"'))
argv = launch.terminal_argv('ghostty', '-e', 'htop # system monitor')
check('a trailing comment does not swallow the shell',
      argv[-1].split('\n')[1] == 'exec "${SHELL:-sh}"', argv)
argv = launch.terminal_argv("my-term --title 'Kachel shell'", '-x', 'ls')
check('the terminal setting is split like a shell would',
      argv[:4] == ['my-term', '--title', 'Kachel shell', '-x'], argv)
try:
    launch.terminal_argv("broken 'quote", '-e', 'ls')
    raised = False
except ValueError:
    raised = True
check('an unbalanced terminal setting raises, for run_in_terminal to report', raised)

section('default_terminal')
terminal, exec_arg = launch.default_terminal()
check('gives a terminal and its exec argument',
      isinstance(terminal, str) and terminal and isinstance(exec_arg, str),
      (terminal, exec_arg))

harness.report()
