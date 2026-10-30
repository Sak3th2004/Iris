export async function api<T=any>(path:string,body?:unknown):Promise<T>{
  const response=await fetch('/api/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'The request could not be completed.');
  return data;
}
