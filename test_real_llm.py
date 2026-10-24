"""Run after installing requirements; tests the REAL provider, no mock."""
import asyncio, json
import httpx

async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        r=await client.post('https://vireonix.ai/v1/chat/completions', json={
            'model':'auto','messages':[{'role':'user','content':'Ответь одним словом: Привет'}],
            'max_tokens':60,'temperature':0.3
        })
        print('HTTP:',r.status_code)
        print('Body:',r.text[:1600])
        r.raise_for_status()
        data=r.json()
        assert data['choices'][0]['message']['content']
        print('REAL LLM RESULT: PASS')

if __name__=='__main__':asyncio.run(main())
