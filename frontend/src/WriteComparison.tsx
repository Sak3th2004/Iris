type Row={resource_type:string;record_id:string;version:number;fields:Record<string,unknown>};
type Permission={resource_type:string;record_id:string;version:number;set_fields:Record<string,unknown>;preserve_fields:Record<string,unknown>};
const show=(value:unknown)=>value===undefined?'Not observed':typeof value==='object'?JSON.stringify(value):String(value);
const equal=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);

export function WriteComparison({permission,proposed,saved}:{permission:Permission;proposed?:Row;saved?:Row}){
  const expected={...permission.preserve_fields,...permission.set_fields};
  const rows=[['Record',`${permission.resource_type} / ${permission.record_id}`,proposed?`${proposed.resource_type} / ${proposed.record_id}`:undefined,saved?`${saved.resource_type} / ${saved.record_id}`:undefined],
    ...Object.entries(expected).map(([key,value])=>[key,value,proposed?.fields[key],saved?.fields[key]])];
  return <section className="write-comparison" aria-label="Authorized, proposed and saved values">
    <div className="section-title"><h3>Permission meets the write.</h3><span>{saved?'Database read-back verified':proposed?'Actual observed form':'Waiting for the first proposal'}</span></div>
    <div className="comparison-scroll"><table><thead><tr><th>Field</th><th>You authorized</th><th>Agent proposed</th><th>Database saved</th></tr></thead><tbody>
      {rows.map(([key,expected,attempt,actual])=><tr key={String(key)}><th>{String(key)}{key!=='Record'&&<small>{String(key) in permission.set_fields?'CHANGE':'PROTECT'}</small>}</th><td>{show(expected)}</td><td className={attempt!==undefined&&!equal(expected,attempt)?'mismatch':''}>{show(attempt)}</td><td className={actual!==undefined?(equal(expected,actual)?'matched':'mismatch'):''}>{actual===undefined?'No save yet':show(actual)}</td></tr>)}
    </tbody></table></div><p className="comparison-version">Permission v{permission.version} · Observed {proposed?'v'+proposed.version:'—'} · Saved {saved?'v'+saved.version:'—'}</p>
  </section>;
}
