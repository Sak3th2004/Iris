"""Inspect only Iris containers and probe the browser's real network boundary."""
import json
import subprocess

def docker(*args):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,check=True)
    return result.stdout.strip()

browser=docker('compose','ps','-q','browser')
owner=docker('compose','ps','-q','owner')
assert browser and owner,'Start Iris first.'
mounts=json.loads(docker('inspect',browser,'--format','{{json .Mounts}}'))
assert len(mounts)==1 and mounts[0]['Type']=='volume' and mounts[0]['Name']=='iris_iris-profile' and mounts[0]['Destination']=='/home/pwuser/iris-profile', 'Browser storage must be only its dedicated profile volume.'
networks=json.loads(docker('inspect',browser,'--format','{{json .NetworkSettings.Networks}}'))
assert list(networks)==['iris_browser'],networks
assert docker('network','inspect','iris_browser','--format','{{.Internal}}')=='true'
owner_network=json.loads(docker('inspect',owner,'--format','{{json .NetworkSettings.Networks}}'))
owner_ip=owner_network['iris_control']['IPAddress']
code='''
import os,socket,json,sys
targets=[('gateway','gateway',8766,True),('public internet','1.1.1.1',443,False),('host owner','host.docker.internal',8768,False),('old host server','host.docker.internal',8765,False),('owner container',sys.argv[1],8765,False)]
assert not os.getenv('MODEL_API_KEY'), 'Provider key leaked to browser'
assert not os.getenv('BASETEN_API_KEY'), 'Reader key leaked to browser'
assert not os.getenv('AWS_ACCESS_KEY_ID') and not os.getenv('AWS_SECRET_ACCESS_KEY'), 'AWS credentials leaked to browser'
assert not os.path.exists('/var/run/docker.sock')
results=[]
for label,host,port,expected in targets:
    try:
        with socket.create_connection((host,port),timeout=2): reachable=True
    except OSError: reachable=False
    results.append({'target':label,'reachable':reachable,'expected':expected})
print(json.dumps(results))
assert all(r['reachable']==r['expected'] for r in results),'Isolation probe failed'
'''
print(docker('compose','exec','-T','browser','python','-c',code,owner_ip))
print('PASS: dedicated profile volume only; no host mounts, provider credentials, Docker socket, owner API, or public egress.')
