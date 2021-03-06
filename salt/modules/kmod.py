'''
Module to manage Linux kernel modules
'''

# Import python libs
import os
import re

def __virtual__():
    '''
    Only runs on Linux systems
    '''
    return 'kmod' if __grains__['kernel'] == 'Linux' else False


def _new_mods(pre_mods, post_mods):
    '''
    Return a list of the new modules, pass an lsmod dict before running
    modprobe and one after modprobe has run
    '''
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod['module'])
    for mod in post_mods:
        post.add(mod['module'])
    return post - pre


def _rm_mods(pre_mods, post_mods):
    '''
    Return a list of the new modules, pass an lsmod dict before running
    modprobe and one after modprobe has run
    '''
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod['module'])
    for mod in post_mods:
        post.add(mod['module'])
    return pre - post

def _union_module(a,b):
    '''
    Return union of two list where duplicated items are only once
    '''
    return list(set(a) | set(b))

def _get_modules_conf():
    '''
    Return location of modules config file.
    Default: /etc/modules
    '''
    return '/etc/modules'

def _strip_module_name(mod):
    '''
    Return module name and strip configuration. It is possible insert modules
    in this format:
        bonding mode=4 miimon=1000
    This method return only 'bonding'
    '''
    if mod.strip() == '':
        return False
    return mod.split()[0]

def _set_persistent_module(mod):
    '''
    Add module to configuration file to make it persistent. If module is
    commented uncomment it.
    '''
    conf = _get_modules_conf()
    mod_name = _strip_module_name(mod)
    if not mod_name or mod_name in mod_list(True) or not mod_name in available():
        return set()
    escape_mod = re.escape(mod)
    ## If module is commented only uncomment it
    if __salt__['file.contains_regex'](conf, "^#[\t ]*{}[\t ]*$".format(escape_mod)):
        __salt__['file.uncomment'](conf, escape_mod)
    else:
        __salt__['file.append'](conf, mod)
    return set([mod_name,])

def _remove_persistent_module(mod, comment):
    '''
    Remove module from configuration file. If comment is true only comment line
    where module is.
    '''
    conf = _get_modules_conf()
    mod_name = _strip_module_name(mod)
    if not mod_name or not mod_name in mod_list(True):
        return set()
    escape_mod = re.escape(mod)
    if comment:
        __salt__['file.comment'](conf, "^[\t ]*{}[\t ]?".format(escape_mod))
    else:
        __salt__['file.sed'](conf, "^[\t ]*{}[\t ]?".format(escape_mod), '')
    return set([mod_name,])

def available():
    '''
    Return a list of all available kernel modules

    CLI Example::

        salt '*' kmod.available
    '''
    ret = []
    mod_dir = os.path.join('/lib/modules/', os.uname()[2])
    for root, dirs, files in os.walk(mod_dir):
        for fn_ in files:
            if '.ko' in fn_:
                ret.append(fn_[:fn_.index('.ko')])
    return sorted(list(ret))


def check_available(mod):
    '''
    Check to see if the specified kernel module is available

    CLI Example::

        salt '*' kmod.check_available kvm
    '''
    return mod in available()


def lsmod():
    '''
    Return a dict containing information about currently loaded modules

    CLI Example::

        salt '*' kmod.lsmod
    '''
    ret = []
    for line in __salt__['cmd.run']('lsmod').splitlines():
        comps = line.split()
        if not len(comps) > 2:
            continue
        if comps[0] == 'Module':
            continue
        mdat = {
            'size': comps[1],
            'module': comps[0],
            'depcount': comps[2],
        }
        if len(comps) > 3:
            mdat['deps'] = comps[3].split(',')
        else:
            mdat['deps'] = []
        ret.append(mdat)
    return ret


def mod_list(only_persist = False):
    '''
    Return a list of the loaded module names

    CLI Example::

        salt '*' kmod.mod_list
    '''
    mods = set()
    if only_persist:
        file = open(_get_modules_conf(), 'r')
        for line in file.readlines():
            line = line.strip()
            mod_name = _strip_module_name(line)
            if not line.startswith('#') and mod_name:
                mods.add(mod_name)
    else:
        for mod in lsmod():
            mods.add(mod['module'])
    return sorted(list(mods))


def load(mod, persist = False):
    '''
    Load the specified kernel module

    mod
        Name of module to add

    persist
        Write module to /etc/modules to make it load on system reboot

    CLI Example::

        salt '*' kmod.load kvm
    '''
    pre_mods = lsmod()
    __salt__['cmd.run_all']('modprobe {0}'.format(mod))
    post_mods = lsmod()
    mods = _new_mods(pre_mods, post_mods)
    persist_mods = set()
    if persist:
        persist_mods = _set_persistent_module(mod)
    return sorted(list(mods | persist_mods))


def remove(mod, persist = False, comment = True):
    '''
    Remove the specified kernel module

    mod
        Name of module to remove

    persist
        Also remove module from /etc/modules

    comment
        If persist is set don't remove line from /etc/modules but only
        comment it

    CLI Example::

        salt '*' kmod.remove kvm
    '''
    pre_mods = lsmod()
    __salt__['cmd.run_all']('modprobe -r {0}'.format(mod))
    post_mods = lsmod()
    mods = _rm_mods(pre_mods, post_mods)
    persist_mods = set()
    if persist:
        persist_mods = _remove_persistent_module(mod, comment)
    return sorted(list(mods | persist_mods))
