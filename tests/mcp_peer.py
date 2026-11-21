"""Independent newline JSON-RPC peer; validates actual MCP lifecycle and types."""
import json,sys
initialized=False
executions=0
for line in sys.stdin:
    request=json.loads(line)
    assert request['jsonrpc']=='2.0'
    method=request['method']
    if method=='notifications/initialized':initialized=True;continue
    assert method=='initialize' or initialized
    if method=='initialize':
        assert request['params']['protocolVersion']=='2025-06-18'
        result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'independent-peer','version':'1'}}
    elif method=='tools/list':
        # stderr can exceed a pipe/socket buffer: the client must drain it.
        sys.stderr.write('diagnostic\n'*20000);sys.stderr.flush()
        print(json.dumps({'jsonrpc':'2.0','method':'notifications/message','params':{'level':'info','data':'ready'}}),flush=True)
        result={'tools':[{'name':'add','inputSchema':{'type':'object','properties':{'a':{'type':'integer'},'b':{'type':'integer'}}}}]}
    elif method=='tools/call':
        if request['params']['name']=='missing':
            print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':'unknown tool'}}),flush=True);continue
        executions+=1;assert executions==1
        args=request['params']['arguments'];assert isinstance(args['a'],int) and isinstance(args['b'],int)
        result={'content':[{'type':'text','text':str(args['a']+args['b'])}],'isError':False}
    elif method=='ping':result=None
    else:raise AssertionError(method)
    wire=json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result},ensure_ascii=False,separators=(',',':'))+'\n'
    # Fragment replies to exercise persistent framing.
    for at in range(0,len(wire),7):sys.stdout.write(wire[at:at+7]);sys.stdout.flush()
