import json
import time
from collections import OrderedDict
from fabric.api import *
from fabric.contrib.files import exists
from os.path import expanduser

env.hosts = open('InstancesConfigurations/public_ips', 'r').read().splitlines()
env.user = 'ubuntu'
# env.password=''
env.key_filename = [expanduser('~/Keys/matrix.pem')]


@task
def pre_process(working_directory, task_idx):
    sudo('apt-get install python3 -y')
    with cd(working_directory):
        put(expanduser('ExperimentExecute/pre_process.py'))
        run('python3 pre_process.py %s' % task_idx)


@task
def install_git_project(git_branch, working_directory, git_address, external):

    if not exists('%s' % working_directory):
        run('git clone %s' % git_address)

    with cd('%s' % working_directory):
        run('git pull')
        run('git checkout %s ' % git_branch)
        if external == 'True':
            with cd('%s/MATRIX' % working_directory):
                run('. ./build.sh')
        else:
            if exists('%s/CMakeLists.txt' % working_directory):
                sudo('rm -rf CMakeFiles CMakeCache.txt Makefile')
                run('cmake .')
            run('make')
            with warn_only():
                sudo('apt install p7zip-full -y')
                run('7za -y x \"*.7z\"')


@task
def update_libscapi(branch):
    with cd('libscapi/'):
        run('git checkout %s' % branch)
        run('git pull')
        run('make')


@task
def run_protocol(config_file, args):
    with open(config_file) as data_file:

        data = json.load(data_file, object_pairs_hook=OrderedDict)
        executable_name = list(data['executableName'].values())
        working_directory = list(data['workingDirectory'].values())
        external_protocol = data['isExternal']
        regions = list(data['regions'].values())
        vals = args.split('@')
        values_str = ''

        for val in vals:
            # for external protocols
            if val == 'partyid':
                values_str += '%s ' % str(env.hosts.index(env.host) - 1)
            else:
                values_str += '%s ' % val

        for idx in range(len(working_directory)):
            with cd(working_directory[idx]):

                party_id = env.hosts.index(env.host)
                with warn_only():
                    sudo("kill -9 `ps aux | grep %s | awk '{print $2}'`" % executable_name[idx])

                if 'inputs0' in values_str:
                    values_str = values_str.replace('input_0.txt', 'input_%s.txt' % str(party_id))

                if external_protocol == 'False':
                    if len(regions) > 1:
                        put('InstancesConfigurations/parties%s.conf' % party_id, run('pwd'))
                        run('mv parties%s.conf parties.conf' % party_id)
                    else:
                        put('InstancesConfigurations/parties.conf', run('pwd'))
                    run('./%s partyID %s %s' % (executable_name[idx], party_id, values_str))

                else:
                    if 'coordinatorConfig' in data and env.hosts.index(env.host) == 0:
                        coordinator_executable = data['coordinatorExecutable']
                        coordinator_args = data['coordinatorConfig'].split('@')
                        coordinator_values_str = ''

                        for coordinator_val in coordinator_args:
                            coordinator_values_str += '%s ' % coordinator_val
                            sudo("kill -9 `ps aux | grep %s | awk '{print $2}'`" % coordinator_executable)
                        run('./%s %s' % (coordinator_executable, coordinator_values_str))

                    else:
                        with cd('MATRIX'):
                            if len(regions) > 1:
                                put('InstancesConfigurations/parties%s.conf' % party_id, run('pwd'))
                                put('InstancesConfigurations/multi_regions/party%s/*' % (party_id - 1), run('pwd'))
                                run('mv parties%s.conf parties.conf' % party_id)
                            else:
                                put('InstancesConfigurations/parties.conf', run('pwd'))

                            run('. ./%s %s %s' % (executable_name[idx], party_id, values_str))


@task
def collect_results(results_server_directory, results_local_directory, is_external):
    local('mkdir -p %s' % results_local_directory)
    if is_external == 'False':
        get('%s/*.json' % results_server_directory, results_local_directory)
    else:
        get('%s/MATRIX/logs/*.log' % results_server_directory, results_local_directory)


@task
def get_logs(working_directory):
    local('mkdir -p logs')
    get('%s/logs/*.log' % working_directory, expanduser('~/MATRIX/logs'))


@task
def update_acp_protocol():
    with cd('ACP'):
        run('git pull https://github.com/cryptobiu/ACP')
        with cd('comm_client'):
            run('cmake .')
            run('make')


@task
def deploy_proxy(number_of_proxies):
    # set hosts to be proxy server
    env.host = ['34.239.19.87']

    # kill all existing proxies
    with warn_only():
        sudo("kill -9 `ps aux | grep cct_proxy | awk '{print $2}'`")

    with cd('ACP/cct_proxy'):
        put('NodeApp/public/assets/parties.conf', run('pwd'))
        with open('NodeApp/public/assets/parties.conf') as parties_file:
            number_of_peers = len(parties_file.readlines())
            run('./run_multiple_proxies %s %s' % ((int(number_of_proxies) - 1), number_of_peers))
