from curses import curs_set
from email.mime import audio
from os import walk, path
from sqlite3 import Cursor
from zipfile import ZipFile
import os
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Project, File, KeyFrame, GameAdvice, Tasks
from .serializers import ProjectTaskModelSerializer,ProjectModelSerializer, FileModelSerializer, GameAdviceModelSerializer, KeyFrameModelSerializer
from rest_framework.decorators import action
from .class_method import *
from django.http import FileResponse
from django.forms.models import model_to_dict
from celery.result import GroupResult




class GameAdviceModelSerializer(ModelViewSet):
    queryset = GameAdvice.objects.all()
    serializer_class = GameAdviceModelSerializer


    """上传文件"""
    # def create(self, request):
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     serializer.save()
    #     print(request._request.FILES.getlist('file'))
    #
    #
    #     return Response(serializer.data, status=status.HTTP_201_CREATED)



class ProcessTaskViewSet(ModelViewSet):
    queryset = Tasks.objects.all()
    serializer_class = ProjectTaskModelSerializer

    '''创建任务'''
    def create(self,request):
        from .tasks import process_video, process_audio
        from celery import group
        # print(request.data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        task = Tasks.objects.get(id = serializer.data['id'])
        # print(task.files['a'],task.files)
        tasks = []
        file_info = serializer.data['files']
        for type,files in file_info.items():
            for file in files:
                if type == 'video':
                    tasks.append(process_video.s(file['id']))
                if type == 'audio':
                    tasks.append(process_audio.s(file['id']))
        task_res = group(tasks).delay()
        task.task_id = task_res.id
        task_res.save()
        task.save()
        return Response({'data':model_to_dict(task),'status':1},status=status.HTTP_200_OK)

    '''任务进度'''
    @action(methods=['GET'],detail=True,url_path='progress')
    def progress(self,request,pk):
        task = Tasks.objects.get(id=pk)
        task_uuid = task.task_id
        task_result = GroupResult.restore(task_uuid)
        res={}
        res['successful'] = task_result.successful()
        res['completed']  = task_result.completed_count()
        res['total'] = len(task_result.results)
        res['ready'] = task_result.ready()
        
        return Response(data=res,status=status.HTTP_200_OK)

    @action(methods=['GET'],detail=True,url_path='result')
    def result(self,request,pk):
        task = Tasks.objects.get(id=pk)
        task_uuid = task.task_id
        task_result = GroupResult.restore(task_uuid)
        if task_result.ready():
            task_result.get()

class FileModelViewSet(ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileModelSerializer



    """上传文件"""
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        print(request._request.FILES.getlist('file'))

        # 如果上传的是zip压缩包，则解压到当前目录
        instance = File.objects.last()
        file = instance.file
        if path.splitext(str(file))[1] == '.zip':
            unzipfile = unzip_file(ZipFile(file))
            unzippath = 'media/files/game_projects/project_{}'.format( instance.project.title)
            with unzipfile as zfp:
                zfp.extractall(unzippath)  # 解压到指定目录
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(methods=['GET'],detail=True,url_path='result')
    def result(self,request,pk):
        file = File.objects.get(id=pk)
        if file.status == 'done':
            return Response({'status':1,'result':file.result},status=status.HTTP_200_OK)
        else :
            return Response({'status':0,'text':'结果未完成处理或处理过程中发生了错误','state':file.status},
            status=status.HTTP_200_OK)

    '''获取已处理好的视频文件处理结果'''
    @action(methods=['GET'],detail=True,url_path='result_video')
    def result_video(self,request,pk):
        from .util import convert_type
        file = File.objects.get(id=pk)
        res = {'status':1}
        type = convert_type(file.file.name)
        if type != 'video':
            res['status'] = -1
            res['text'] = '文件类型错误，预期文件类型：video，接收到：{}'.format(type)
            return Response(res,status=status.HTTP_200_OK)
        if file.status == 'done':
            keyframes = file.video_keyframes.all()
            def renamedict(frames):
                for frame in frames:
                    dict = model_to_dict(frame,exclude=['file'])
                    dict['timestamp'] = dict.pop('time')
                    dict['src'] = dict.pop('path')
                    dict['description'] = dict.pop('result')['is_blood']
                    yield dict
            res['keyframes'] = list(renamedict(keyframes))

            return Response(res,status=status.HTTP_200_OK)
        else :
            return Response({'status':0,'text':'结果未完成处理或处理过程中发生了错误','state':file.status},
            status=status.HTTP_200_OK)


class ProjectModelViewSet(ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectModelSerializer



    """添加一个项目"""
    def create(self, request):
        print(type(request.data), request.data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        for f in request.FILES.getlist('files[]'):
            from .util import calculate_file_hash
            # This looks not so right, could have cause some undesire behaviors....
            hashcode = calculate_file_hash(f)  
            instance = File(file=f ,project=Project.objects.last(),md5=hashcode)
            instance.save()
            print(f,'111',instance,'111',instance.file.path)
            from .util import convert_type,generate_video_cover
            if convert_type(instance.file.path) == 'video':
                # Generate a video cover
                generate_video_cover(instance)
        return Response({'status':1}, status=status.HTTP_201_CREATED)




    """获取一个项目"""
    def retrieve(self, request, pk):
        from . import class_method
        instance = self.get_object()
        serializer = self.get_serializer(instance=instance)

        instance = Project.objects.get(id=pk)
        path = 'media/files/game_projects/project_{}'.format(instance.title)
        res={}
        files = instance.project_files.all()
        filelist = []
        advicelist = []
        # print(files)
        from .util import convert_size, convert_type
        for f in files:
            from .util import get_file_info
            filelist.append(get_file_info(f))
        advices = instance.advice_files.all()
        for advf in advices:
            advicelist.append({'id':advf.id,'url':advf.file.url})
        res['fileList'] = filelist
        res['healthyReminder'] = advicelist
        # Does not needed...
        # img_data_file = get_img(path)
        # doc_data_file = get_doc(path)
        # res['file_num'] = len(img_data_file)+len(doc_data_file)
        # res['img_num'] = len(img_data_file)
        # res['doc_num'] = len(doc_data_file)
        # res['audio_num'] = len(audio_data_file)
        # res['img_data_file'] = img_data_file
        # res['doc_data_file'] = doc_data_file
        # res['audio_data_file'] = audio_data_file
        serializer.data['res'] = res
        res.update(serializer.data)

        return Response(res, status=status.HTTP_201_CREATED)



    """删除一个项目"""
    def destroy(self, request, pk):

        # 删除该项目所有文件
        import shutil
        instance = Project.objects.get(id=pk)
        path = 'media/files/game_projects/project_{}'.format(instance.title)
        if os.path.exists(path):
            shutil.rmtree(path)

       # 删除项目
        self.get_object().delete()
        return Response({'mes': '删除成功'}, status=status.HTTP_200_OK)

    '''获取媒体文件（视频）'''
    @action(methods=['get'],detail=True, url_path='media_file')
    def get_media_files(self,request,pk):
        fid = request.GET.get('fid')
        file_path = File.objects.get(id=fid).file.path
        open_file = open(file_path,'rb')
        response = FileResponse(open_file)
        file_size = os.path.getsize(file_path)
        response['Content-Range'] = f'bytes 0-{str(file_size)}/{str(file_size)}'
        response['Accept-Ranges'] = 'bytes'
        return response

    '''获取项目所有图片文件'''
    @action(methods=["get"], detail=True, url_path="images")
    def get_img_files(self, request, pk):
        from .util import convert_type
        instance = Project.objects.get(id=pk)
        serializer = ProjectModelSerializer(instance=instance)
        instance_file = serializer.data['project_files']

        image_file = [{'id': file['id'], 'file':os.path.basename(file['file']), 'project':file['project']}
                                  for file in instance_file if convert_type(os.path.basename(file['file'])) == 'image']


        if len(image_file) == 0:
            return Response({'res': "项目没有图片文件"}, status=status.HTTP_200_OK)

        return Response(data=image_file, status=status.HTTP_200_OK)

    '''获取项目游戏建议图片文件'''
    @action(methods=["get"], detail=True, url_path="advice_images")
    def get_advice_img_files(self, request, pk):
        from .util import convert_type
        instance = Project.objects.get(id=pk)
        serializer = ProjectModelSerializer(instance=instance)
        instance_advice_file = serializer.data['advice_files']
        for file in instance_advice_file:
            print (file['file'])
        advice_image = [{'url':file['file'],'id': file['id'], 'file':os.path.basename(file['file']), 'project':file['project']}
                                  for file in instance_advice_file if convert_type(os.path.basename(file['file'])) == 'image']

        if len(advice_image) == 0:
            return Response({'status':0,'res': "项目没有图片文件"}, status=status.HTTP_200_OK)

        return Response(data={'data':advice_image,'status':1}, status=status.HTTP_200_OK)


    '''删除项目游戏健康忠告图片'''
    @action(methods=["delete"], detail=True, url_path="delete_advice_images")
    def delete_advice_img_file(self, request, pk):
        project_advices_ids=Project.objects.get(id=pk).advice_files.all().values_list('id',flat=True)
        # {
        #  "delete":[1] 
        # }
        deletedfid=[]
        fid = dict(eval(request.body))['delete'][0]
        if fid in project_advices_ids:
            instance = GameAdvice.objects.get(id=fid)
            if os.path.exists(instance.file.path):
                os.remove(instance.file.path)
            instance.delete()
            deletedfid.append(fid)
            return Response(data={'status':1,'deletedfid':deletedfid}, status=status.HTTP_200_OK)
        else:
            return Response(data={'status':0,'deletedfid':deletedfid}, status=status.HTTP_200_OK)

    '''获取项目所有文本文件'''
    @action(methods=["get"], detail=True, url_path="texts")
    def get_text_files(self, request, pk):
        from .util import convert_type
        instance = Project.objects.get(id=pk)
        serializer = ProjectModelSerializer(instance=instance)
        instance_file = serializer.data['project_files']
        text_file = [{'id': file['id'], 'file':os.path.basename(file['file']), 'project':file['project']}
                                  for file in instance_file if convert_type(os.path.basename(file['file'])) == 'text']

        if len(text_file) == 0:
            return Response({'res': "项目没有文本文件"}, status=status.HTTP_200_OK)

        return Response(data=text_file, status=status.HTTP_200_OK)

    '''删除项目文件'''
    @action(methods=['delete'],detail=True, url_path="delete_files")
    def delete_project_files(self,request,pk):
        project = Project.objects.get(id=pk)
        project_files = project.project_files.all().values_list('id',flat=True)
        deletedfid=[]
        for fid in dict(eval(request.body))['delete']:
            if fid in project_files:
                # The file belongs to the project
                file = File.objects.get(id = fid)
                if os.path.exists(file.file.path):
                    import shutil
                    os.remove(file.file.path)
                file.delete()
                deletedfid.append(fid)
        print(deletedfid)
        return Response({'deletedfid':deletedfid,'status':0 if len(deletedfid)==0 else 1},status=status.HTTP_200_OK)


    '''上传新的项目文件'''
    @action(methods=['POST'], detail=True, url_path="upload") 
    def upload_new_files(self,request,pk):
        from .util import calculate_file_hash
        uploaded = 0
        filecount = len(request.FILES.getlist('files[]'))
        project = Project.objects.get(id=pk)
        current_files_md5=project.project_files.all().values_list('md5',flat=True)
        # print(current_files_md5)
        file_rejected=[]
        for f in request.FILES.getlist('files[]'):
            hashcode = calculate_file_hash(f)
            if hashcode in current_files_md5:
                print('found')
                file_rejected.append(f.name)
                continue
            instance = File(file=f ,project=project,md5=hashcode)
            instance.save()
            # print(f,'111',instance,'111',instance.file.path)
            from .util import convert_type,generate_video_cover
            if convert_type(instance.file.path) == 'video':
                # Generate a video cover
                generate_video_cover(instance)
            uploaded+=1
        return Response({'status':1 if uploaded>0 else 0,'file_rejected':file_rejected,
        'fileuploaded':uploaded,'text':'共上传了{0}个文件中的{1}个'.format(filecount,uploaded)}
        ,status=status.HTTP_200_OK)


    '''获取项目所有音频文件'''
    @action(methods=["get"], detail=True, url_path="audios")
    def get_audio_files(self, request, pk):
        from .util import convert_type
        instance = Project.objects.get(id=pk)
        serializer = ProjectModelSerializer(instance=instance)
        instance_file = serializer.data['project_files']
        audio_file = [{'id': file['id'], 'file':os.path.basename(file['file']), 'project':file['project']}
                                  for file in instance_file if convert_type(os.path.basename(file['file'])) == 'audio']

        if len(audio_file) == 0:
            return Response({'res': "项目没有音频文件"}, status=status.HTTP_200_OK)

        return Response(data=audio_file, status=status.HTTP_200_OK)


    '''获取项目所有视频文件'''
    @action(methods=["get"], detail=True, url_path="videos")
    def get_video_files(self, request, pk):
        from .util import convert_type
        instance = Project.objects.get(id=pk)
        serializer = ProjectModelSerializer(instance=instance)
        instance_file = serializer.data['project_files']
        video_file = [{'id': file['id'], 'file':os.path.basename(file['file']), 'project':file['project']}
                                  for file in instance_file if convert_type(os.path.basename(file['file'])) == 'video']

        if len(video_file) == 0:
            return Response({'res': "项目没有视频文件"}, status=status.HTTP_200_OK)

        return Response(data=video_file, status=status.HTTP_200_OK)



    '''获取一张图片'''
    # @action(methods=["get"], detail=True, url_path="process_img")
    def get_one_img(self, request, pk, file_id):
        from PIL import Image
        instance = Project.objects.get(id=pk)

        file = File.objects.filter(id=file_id)[0]
        path = file.file

        image = Image.open(path).convert('RGB')
        context = img_base64(image)

        return Response({'image': context}, status=status.HTTP_200_OK)

    '''获取一张游戏建议图片'''
    # @action(methods=["get"], detail=True, url_path="process_img")
    def get_one_advice_img(self, request, pk, file_id):
        from PIL import Image
        instance = Project.objects.get(id=pk)

        file = GameAdvice.objects.filter(id=file_id)[0]
        path = file.file

        image = Image.open(path).convert('RGB')
        context = img_base64(image)

        return Response({'image': context}, status=status.HTTP_200_OK)




    '''获取一个文档'''
    # @action(methods=["get"], detail=True, url_path="process_img")
    def get_one_doc(self, request, pk, file_id):
        import docx
        instance = Project.objects.get(id=pk)
        file = File.objects.get(id=file_id)
        path = file.file
        content_str = ''
        file = docx.Document(path)
        for para in file.paragraphs:
            content_str += str(para.text)

        return Response({'text': content_str}, status=status.HTTP_200_OK)


    '''获取一个音频'''
    # @action(methods=["get"], detail=True, url_path="process_audio")
    def get_one_audio(self, request, pk, file_id):
        instance = Project.objects.get(id=pk)
        audiofile = File.objects.get(id=file_id)
        file_path = audiofile.file
        
        return Response({'audio': str(file_path)}, status=status.HTTP_200_OK)


    '''获取一个视频'''
    # @action(methods=["get"], detail=True, url_path="process_audio")
    def get_one_video(self, request, pk, file_id):
        instance = Project.objects.get(id=pk)
        videofile = File.objects.get(id=file_id)
        file_path = videofile.file
        KeyFrame.objects.all().delete()
        
        return Response({'video': str(file_path)}, status=status.HTTP_200_OK)


    '''获取一个关键帧'''
    def get_one_frame(self, request, pk, file_id, frame_id):
        instance = Project.objects.get(id=pk)
        videofile = File.objects.get(id=file_id)
        keyframe = KeyFrame.objects.get(id=frame_id)
        frame_path = keyframe.path
        
        
        return Response({'frame': str(frame_path)}, status=status.HTTP_200_OK)



    '''处理一张图片'''
    # @action(methods=["get"], detail=True, url_path="process_img")
    def process_img(self, request, pk, file_id):

        instance = Project.objects.get(id=pk)
        file = File.objects.get(id=file_id)
        path = file.file

        # # 开始处理图片
        imgfilter = ImageProcess()
        imgfilter.init_para(path)
        imgfilter.process_traditional_characters()
        imgfilter.process_sensitive_word()
        imgfilter.process_english_word()
        imgfilter.process_skull()
        imgfilter.process_blood(path)
        # imgfilter.image.show()
        res = imgfilter.process_result

        return Response(data=res, status=status.HTTP_200_OK)



    '''处理一张图片(健康游戏忠告)'''
    # @action(methods=["get"], detail=True, url_path="game_advice")
    def game_advice(self, request, pk, file_id):
        instance = Project.objects.get(id=pk)
        file = GameAdvice.objects.get(id=file_id)
        path = file.file

        # # 开始处理图片
        imgfilter = ImageProcess()
        imgfilter.init_para(path)
        imgfilter.game_advice()
        res = imgfilter.process_result
        
        return Response(data=res, status=status.HTTP_200_OK)
       

        




    '''处理一个文档'''
    # @action(methods=["get"], detail=True, url_path="process_doc")
    def process_doc(self, request, pk, file_id):

        instance = Project.objects.get(id=pk)
        file = File.objects.get(id=file_id)
        path = file.file.path

        # # 开始处理
        docfilter = DocProcess()
        docfilter.init_para(path)
        docfilter.process_traditional_characters()
        docfilter.process_sensitive_word()
        docfilter.process_english_word()

        res = docfilter.process_result

        return Response(data=res, status=status.HTTP_200_OK)


    '''处理一个音频'''
    # @action(methods=["get"], detail=True, url_path="process_audio")
    def process_audio(self, request, pk, file_id):

        instance = Project.objects.get(id=pk)
        file = File.objects.get(id=file_id)
        path = './media/' + str(file.file)

        speechfilter = SpeechProcess()
        speechfilter.init_para(path)
        speechfilter.process_sensitive_word()
        speechfilter.process_english_word()

        res = speechfilter.process_result
  
        return Response(data=res, status=status.HTTP_200_OK)


    '''处理一个视频'''
    # @action(methods=["get"], detail=True, url_path="process_audio")
    def key_frames(self, request, pk, file_id):
        instance = Project.objects.get(id=pk)
        file = File.objects.get(id=file_id)
        path = './media/' + str(file.file)
        if file.status == 'uploaded' or request.GET.get('force').lower() == 'true':    
            #清除原来的关键帧
            file.video_keyframes.all().delete()
            #开始抽取关键帧
            vediofilter = VideoProcess()
            vediofilter.extract_frame(path)
            key_frame = zip(vediofilter.frame,vediofilter.frame_time, vediofilter.frame_path)
            #保存关键帧到数据库
            for i,j,k in key_frame:
                new_keyframe = KeyFrame.objects.create()
                new_keyframe.file = file
                new_keyframe.path = k
                new_keyframe.time = j
                new_keyframe.frame = i
                new_keyframe.save()
            file.status = 'ready'
            file.save()
        all_key = file.video_keyframes.all()
        res = [{'id': file.id, 'description': '视频关键帧，用于后续的各项检测','frame':file.frame ,'timestamp':file.time , 'src':file.path, } for file in all_key ]

        return Response(data=res, status=status.HTTP_200_OK)

    
    '''获取任务结果'''
    def get_task_result(self,request):
        task_id = request.POST.get('task_id')
        from backend.celery import app
        res = app.AsyncResult(task_id)
        if res.state == 'SUCCESS':
            ret = res.get()
        else :
            ret = {'info':'Result not ready','state':res.state}
        return Response(data = ret, status=status.HTTP_200_OK)

    '''处理一个关键帧(测试任务队列)'''
    def process_frame_task(self, request, pk, file_id, frame_id):
        from .tasks import process_frame
        instance = Project.objects.get(id=pk)
        videofile = File.objects.get(id=file_id)
        res = process_frame.delay(frame_id)
        print(res)
        print(res.id)


        return Response(data=res.id, status=status.HTTP_200_OK)

    '''处理一个关键帧'''
    def process_frame(self, request, pk, file_id, frame_id):
        instance = Project.objects.get(id=pk)
        videofile = File.objects.get(id=file_id)
        keyframe = KeyFrame.objects.get(id=frame_id)
        frame_path = keyframe.path

        #  开始处理关键帧
        imgfilter = ImageProcess()
        imgfilter.init_para(frame_path)
        imgfilter.process_blood(frame_path)
        res = imgfilter.process_result


        return Response(data=res, status=status.HTTP_204_NO_CONTENT)




    '''链接数据库并获取数据'''
    @action(methods=["post"], detail=False, url_path="testdb")
    def testdb(self, request):
        dbcursor = DBConnection(user='root',pwd='123456',)

    '''链接数据库并获取数据'''
    @action(methods=["post"], detail=False, url_path="conndb")
    def conndb(self, request):
        import pandas as pd
        form_data=request.data
        # request._request.session['user'] = form_data['user']
        # request._request.session['pwd'] = form_data['pwd']
        # request._request.session['dbname'] = form_data['dbname']
        # request._request.session['tablename'] = form_data['tablename']
 
        dbcursor = DBConnection(user=form_data['user'],pwd=form_data['pwd'],dbname=form_data['dbname'],tablename=form_data['tablename'])
        dbcursor.conn()
        data = dbcursor.get_data()
        formheader = dbcursor.formheader
        df = pd.DataFrame(data[1000:1500],columns=formheader)
      
        print(df.values)

        res = {'table':[],'suggestion':[]}

        for row in df.values:
            row_dic={}
            for i,j in enumerate(row):
                row_dic[formheader[i]]=j
            res['table'].append(row_dic)


        nametemplate = "在{0}行的{1}列中发现敏感姓名信息。"
        addresstemplate = "在{0}行的{1}列中发现敏感地址信息。"
        phonetemplate = "在{0}行的{1}列中发现敏感电话号码信息。"
        agetemplate = "在{0}行的{1}列中发现敏感年龄信息。"
        suggcount=0



        if 'name' in formheader:
            col=formheader.index('name')
            for i,item in enumerate(df.values[:,col]) :
                if not item.count('*'):
                    sug={
                        'id':suggcount+1,
                        'rowid':i,
                        'column':'name',
                        'seriousness':'high',
                        'title':'发现敏感姓名数据',
                        'description':nametemplate.format(i,'name'),
                    }
                    suggcount+=1
                    res['suggestion'].append(sug)


        if 'address' in formheader:
            col=formheader.index('address')
            for i,item in enumerate(df.values[:,col]) :
                if not item.count('*'):
                    sug={
                        'id':suggcount+1,
                        'rowid':i,
                        'column':'address',

                        'seriousness':'medium',
                        'title':'发现敏感地址数据',
                        'description':addresstemplate.format(i,'address'),
                    }
                    suggcount+=1
                    res['suggestion'].append(sug)


        if 'phone_number' in formheader:
            col=formheader.index('phone_number')
            for i,item in enumerate(df.values[:,col]) :
                if not item.count('*'):
                    sug={
                        'id':suggcount+1,
                        'rowid':i,
                        'column':'phone_number',

                        'seriousness':'high',
                        'title':'发现敏感电话号码数据',
                        'description':phonetemplate.format(i,'phone_number'),
                    }
                    suggcount+=1
                    res['suggestion'].append(sug)


        if 'age' in formheader:
            col=formheader.index('age')
            for i,item in enumerate(df.values[:,col]) :
                if  item != 'nan':
                    sug={
                        'id':suggcount+1,
                        'rowid':i,
                        'column':'age',
                        'seriousness':'low',
                        'title':'发现敏感年龄数据',
                        'description':agetemplate.format(i,'age'),
                    }
                    suggcount+=1
                    res['suggestion'].append(sug)
               
        return Response( data={'data':res},status=status.HTTP_201_CREATED)
    