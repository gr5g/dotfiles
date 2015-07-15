#!/usr/bin/env python


from __future__ import with_statement
import os
import re
import platform
import yaml
from fabric.api import sudo, run, settings, task
from fabric.contrib.files import exists


@task
def git_config(user, email):
    run("git config --global color.ui true")
    run("git config --global user.name %s" % user)
    run("git config --global user.email %s" % email)


@task
def sshd_rsa_auth():
    run("sudo -v")
    run("ssh-keygen -t rsa")
    run("mv ~/.ssh/id_rsa.pub ~/.ssh/authorized_keys")
    run("chmod 600 ~/.ssh/authorized_keys")
    sudo("sed -ie 's/^\(PasswordAuthentication\s\+\)yes$/\\1no/' /etc/ssh/sshd_config")
    sudo("systemctl restart sshd")


@task
def wheel_nopass_sudo():
    run("sudo -v")
    sudo("sed -ie 's/^#\s\+\(%wheel\s\+ALL=(ALL)\s\+NOPASSWD:\s\+ALL\)$/\\1/' /etc/sudoers")
    sudo("usermod -G wheel %s" % run("whoami"))


@task
def init_dev():
    with open('config.yml') as f:
        env_config = yaml.load(f)
    pkg_mng(env_config)
    lang_env(env_config)
    zsh_vim_env()


def pkg_mng(env_config):
    os_type = platform.system()
    if os_type == 'Linux':
        if run("sudo -v", warn_only=True).succeeded:
            if sudo("dnf --version", warn_only=True).succeeded:
                pm = 'dnf'
            elif sudo("yum --version", warn_only=True).succeeded:
                pm = 'yum'
            else:
                pm = False

            if pm:
                sudo("%s -y upgrade" % pm)
                sudo("%s -y install %s" % (pm, ' '.join(env_config['dnf'])))
                sudo("%s -y groupinstall '%s'" % (pm, '\' \''.join(env_config['dnf_group'])))
    elif os_type == 'Darwin':
        if run("brew --version", warn_only=True).failed:
            run("ruby -e '$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)'")
        else:
            run("brew update && brew upgrade --all")
        map(lambda p: run("brew install %s" % p), env_config['brew'])


def lang_env(env_config):
    if not exists('~/.pyenv'):
        run("git clone https://github.com/yyuu/pyenv.git ~/.pyenv")
    else:
        run("cd ~/.pyenv && git pull && cd -")

    if not exists('~/.rbenv'):
        run("git clone https://github.com/sstephenson/rbenv.git ~/.rbenv")
        run("git clone https://github.com/sstephenson/ruby-build.git ~/.rbenv/plugins/ruby-build")
    else:
        run("cd ~/.rbenv && git pull && cd -")
        run("cd ~/.rbenv/plugins/ruby-build && git pull && cd -")

    with settings(warn_only=True):
        py = {'env': '~/.pyenv/bin/pyenv', 'mng': '~/.pyenv/shims/pip'}
        rb = {'env': '~/.rbenv/bin/rbenv', 'mng': '~/.rbenv/shims/gem'}

        for l in ({'lang': py, 'ver': env_config['ver']['py2']},
                  {'lang': py, 'ver': env_config['ver']['py3']},
                  {'lang': rb, 'ver': env_config['ver']['rb']}):
            if run("%s versions | grep -o -e '\\s%s'" % (l['lang']['env'], l['ver'])).failed:
                run("%s install %s" % (l['lang']['env'], l['ver']))
                run("%s rehash" % l['lang']['env'])

            run("%s global %s" % (l['lang']['env'], l['ver']))
            if l['lang'] == py:
                run("%s list | cut -f 1 -d ' ' | xargs -n 1 %s install -U" % (py['mng'], py['mng']))
                map(lambda p: run("%s install %s" % (py['mng'], p)), env_config['pip'])
            elif l['lang'] == rb:
                run("%s update" % rb['mng'])
                map(lambda p: run("%s install --no-document %s" % (rb['mng'], p)), env_config['gem'])

        if run("go version").succeeded:
            if not exists('~/go'):
                run("mkdir ~/go")
            run("go get -u all")
            map(lambda p: run("go get -v %s" % p), env_config['go'])

        if run("R --version").succeeded:
            run("R -q --vanilla < ~/dotfiles/pkg_install.R")


def zsh_vim_env():
    dot_files = ('.zshrc', '.zshenv', '.vimrc')
    if not exists('~/dotfiles'):
        run("git clone https://github.com/dceoy/dotfiles.git ~/dotfiles")
    map(lambda f: run("ln -s ~/dotfiles/%s ~/%s" % ('d' + f, f)), filter(lambda f: not exists("~/%s" % f), dot_files))

    if not re.match(r'.*\/zsh$', os.getenv('SHELL')):
        run("chsh -s `grep -e '\/zsh$' /etc/shells | tail -1` `whoami`")

    if not exists('~/.vim/bundle/neobundle.vim'):
        run("mkdir -p ~/.vim/bundle")
        run("git clone https://github.com/Shougo/neobundle.vim ~/.vim/bundle/neobundle.vim")
    else:
        run("cd ~/.vim/bundle/neobundle.vim && git pull && cd -")

    run("vim -c NeoBundleUpdate -c q")
    run("vim -c NeoBundleInstall -c q")


if __name__ == '__main__':
    print("Usage: fab [options] <command>[:arg1,arg2=val2,host=foo,hosts='h1;h2',...] ...")
