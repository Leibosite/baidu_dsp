# baidu_dsp
与百度adx对接


一、rquest
安装步骤：
    1. 安装protobuf 及python 环境
        在 http://code.google.com/p/protobuf/ 下载源码
        tar -zxvf protobuf-2.4.1.tar.gz (需要高于2.4.1)
        cd protobuf-2.4.1;
		./autogen.sh (如果无法下载gmock，安装本地tar包，并修改autogen.sh脚本，重新执行)
        ./configure ( 如果目录没有权限的话, 请加上--prefix=<path> )
        make;
        make install;
        cd python;
        python setup.py install ( 如果没有python，请自己安装，如果提示缺少setuptool，按以下步骤执行
			1.下载或使用本地安装包wget http://pypi.python.org/packages/source/s/setuptools/setuptools-0.6c11.tar.gz；
			2.python setup.py build；
			3.python setup.py install) 
    2. 进入request目录编译 baidu_realtime_bidding.proto  协议文件
        直接在当前目录执行make
        如果协议文件有更新，请重新make
使用方法：
    1. 测试单一请求：
        python requester.py  --url=<url>  --max_qps=1 --requests=1 --mobile_proportion=0.1 
    2. 测试多个请求, 用max_qps控制负载， 用--requests或者--seconds控制时间 mobile_proportion控制mobile请求比
        python requester.py  --url=<url>  --max_qps=<max_qps> --requests=100 --mobile_proportion=0.2 
        python requester.py  --url=<url>  --max_qps=<max_qps> --seconds=100 
    3. 输出文件，记录竞价信息：
        *   good-<timestamp>.log  
            记录竞价成功的请求和返回
        *   error-<timestamp>.log 
            记录http 返回码不为200的请求
        *   invalid-<timestamp>.log
            记录无法正确解析的请求
        *   problematic-<timestamp>.log
            记录存在问题的请求及返回 
			
二、response