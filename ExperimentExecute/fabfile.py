import json
import sys

from fabric.api import *
from fabric.contrib.files import exists
from os.path import expanduser

env.hosts = open('public_ips', 'r').read().splitlines()
env.user = 'ubuntu'
env.key_filename = [expanduser('~/Keys/matrix.pem')]


@task
def pre_process():
    put('ExperimentExecute/pre_process.py', '~')
    run('python3 pre_process.py')

# @task
# def pre_process(experiment_name):
#     with cd('/home/ubuntu/%s' % experiment_name):
#         if exists('pre_process.py'):
#             run('python 3 pre_process.py')


@task
def install_git_project(experiment_name, git_branch, working_directory):

    if not exists('%s' % working_directory):
        run('git clone https://liorbiu:4aRotdy0vOhfvVgaUaSk@github.com/cryptobiu/%s.git' % experiment_name)

    if experiment_name == 'LowCostConstantRoundMPC':
        put(expanduser('~/Desktop/libOTe.tar.gz'))
        run('tar -xf libOTe.tar.gz')
        with cd('libOTe'):
            run('rm -rf CMakeFiles CMakeCache.txt Makefile')
            run('cmake .')
            run('make')

    with cd('%s' % working_directory):
        run('git checkout %s ' % git_branch)
        run('cmake .')
        run('make')


@task
def update_git_project(experiment_name, git_branch, working_directory):

    with cd('%s' % working_directory):
        run('git pull')
        sudo('rm -rf CMakeFiles CMakeCache.txt Makefile')
        run('cmake .')
        run('make')


@task
def update_libscapi():
    with cd('libscapi/'):
        run('git pull')
        run('cmake .')
        sudo('make')


@task
def run_protocol(config_file):
    with open(config_file) as data_file:
        data = json.load(data_file)
        protocol_name = data['protocol']
        executable_name = data['executableName']
        configurations = data['configurations']
        working_directory = data['workingDirectory']

        sudo('rm -f ~/libscapi/protocols/GMW/*.json')

        # list of all configurations after parse
        lconf = list()
        for i in range(len(configurations)):
            vals = configurations.values()
            values_str = ''

            for val in vals:
                values_str += val

            lconf.append(values_str)

        with cd(working_directory):
            put('parties.conf', run('pwd'))

            party_id = env.hosts.index(env.host)
            print(party_id)

            for idx in range(len(lconf)):
                if protocol_name == 'GMW':
                    lconf[idx] = lconf[idx].replace('AesInputs0.txt', 'AesInputs%s.txt' % str(party_id))

                run('./%s -partyID %s %s' % (executable_name, party_id, lconf[idx]))

    sys.stdout.flush()


@task
def collect_results(results_local_directory, results_remote_directory):

    local('mkdir -p %s' % results_remote_directory)
    get('%s/*.json' % results_local_directory, results_remote_directory)