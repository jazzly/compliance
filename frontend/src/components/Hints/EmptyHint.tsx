import React from 'react'
import { Empty } from 'antd'
import { Typography } from '@mui/material'

type Props={
  text:string
}

export default function EmptyHint({text}:Props) {
  return (
    <div style={{height:'100%',width:'fill-available',display:'flex',alignItems:"center",justifyContent:'center'}}>
      <Empty
        description={
          <Typography component='div' color="#a9a9a9" align='center' lineHeight='100%'>{text}</Typography>
        }
      />
        
    </div>
  )
}
