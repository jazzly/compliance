import React, { Component, createRef } from 'react'
import { Grid, Step, Stepper, StepButton, Divider, Stack, Typography, StepContent, IconButton } from '@mui/material'
import Titles from '../../typography/Titles'
import Paragraphs from '../../typography/Paragraphs'
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import HourglassBottomIcon from '@mui/icons-material/HourglassBottom';
import GppGoodIcon from '@mui/icons-material/GppGood';
import EmptyHint from '../../Hints/EmptyHint';
import HealthyReminder from './subComponents/CheckListContents/HealthyReminder';
import TextSummary from './subComponents/CheckListContents/TextSummary';

export default class ProjectCheckList extends Component {
    constructor(props){
        super(props)
        this.state = {
            activeStep:-1,
            completed:{}
        }
    }
    
    handlePreviousNext=(isPrevious)=>(e)=>{
        let step = 1
        if(isPrevious){
            step = -step
        }
        this.setState({
            activeStep:this.state.activeStep+step
        })
    }

    handleStep = (index)=>(e)=>{
        this.setState({
            activeStep: index
        })
    }

render() {
    let {fileCount,healthyReminder,pid} = this.props.info

    let steps = [
        {
            label:'图片检测',
            description:'Some description here'
        },
        {
            label:'文本检测',
            description:'Some description here',
            content:<TextSummary fileCount={fileCount}></TextSummary>
        },
        {
            label:'数据库检测',
            description:'Some description here'
        },
        {
            label:'音频检测',
            description:'Some description here'
        },
        {
            label:'游戏健康忠告',
            description:'检测游戏启动过程中是否含有游戏健康忠告信息',
            content:<HealthyReminder file={healthyReminder} pid={pid}/>
        },
    ]
     
    let {activeStep} = this.state
    let header =
    <Stack direction='row' justifyContent='space-between' alignItems='center' sx={{p:2}}>
        <IconButton color='primary' disabled={activeStep===0} onClick={this.handlePreviousNext(true)}><ArrowBackIosNewIcon/></IconButton>
        {activeStep>=0 && <Titles>{steps[activeStep].label}</Titles>}
        <IconButton color='primary' disabled={activeStep===steps.length-1} onClick={this.handlePreviousNext(false)}><ArrowForwardIosIcon/></IconButton>
    </Stack>
    let content = activeStep>=0 ? steps[activeStep].content??<EmptyHint text='暂时没有内容'></EmptyHint>:<></>
    let detail = <Stack height='100%' paddingBottom={4}>
        {header}
        <Divider flexItem/>
        {content}
    </Stack>
    return (
        <Grid container sx={{height:'100%',maxWidth:'100%'}}>
            <Grid item xs={4} sx={{height:'100%'}}>
                <Stack justifyContent="spcae-between" alignItems="center" spacing={2} sx={{py:2}}>
                    <Titles>审核项目</Titles>
                    <Divider orientation='horizontal' flexItem/>
                </Stack>
                <Stepper orientation='vertical' nonLinear activeStep={this.state.activeStep} sx={{px:2}}>
                    {steps.map((step,index)=>(
                        <Step key={step.label} completed={this.state.completed[index]} >
                            <StepButton color="inherit" onClick={this.handleStep(index)}>
                                {step.label}
                            </StepButton>
                            <StepContent>
                                <Paragraphs>{step.description}</Paragraphs>
                            </StepContent>
                        </Step>
                    ))}
                </Stepper>
            </Grid>
                <Divider orientation='vertical' flexItem sx={{height:'100%'}}/>
            <Grid item xs alignItems='center' justifyContent='center' sx={{height:'100%',px:2}}>  
                {this.state.activeStep===-1?<EmptyHint text={'在左侧列表中选择一个项目以查看详情'}/>:detail}
                
            </Grid>
      </Grid>
    )
  }
}


