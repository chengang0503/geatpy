# -*- coding: utf-8 -*-
import geatpy as ea # 导入geatpy库
from sys import path as paths
from os import path as path
paths.append(path.split(path.split(path.realpath(__file__))[0])[0])

class moea_NSGA3_DE_templet(ea.MoeaAlgorithm):
    
    """
moea_NSGA3_DE_templet : class - 多目标进化优化NSGA-III-DE算法模板
    
算法描述:
    采用NSGA-III-DE进行多目标优化，
    与NSGA-III不同的是，该算法把NSGA-III中的子代生成部分替换成DE/rand/1/bin。
    注意：在初始化染色体时，种群规模会被修正为NSGA-III所用的参考点集的大小。

模板使用注意:
    本模板调用的目标函数形如：aimFunc(pop), 
    其中pop为Population类的对象，代表一个种群，
    pop对象的Phen属性（即种群染色体的表现型）等价于种群所有个体的决策变量组成的矩阵，
    该函数根据该Phen计算得到种群所有个体的目标函数值组成的矩阵，并将其赋值给pop对象的ObjV属性。
    若有约束条件，则在计算违反约束程度矩阵CV后赋值给pop对象的CV属性（详见Geatpy数据结构）。
    该函数不返回任何的返回值，求得的目标函数值保存在种群对象的ObjV属性中，
                          违反约束程度矩阵保存在种群对象的CV属性中。
    例如：population为一个种群对象，则调用aimFunc(population)即可完成目标函数值的计算，
         此时可通过population.ObjV得到求得的目标函数值，population.CV得到违反约束程度矩阵。
    若不符合上述规范，则请修改算法模板或自定义新算法模板。

参考文献:
    [1] Deb K , Jain H . An Evolutionary Many-Objective Optimization Algorithm 
    Using Reference-Point-Based Nondominated Sorting Approach, Part I: 
    Solving Problems With Box Constraints[J]. IEEE Transactions on 
    Evolutionary Computation, 2014, 18(4):577-601.
    
    [2] Tanabe R., Fukunaga A. (2014) Reevaluating Exponential Crossover in 
    Differential Evolution. In: Bartz-Beielstein T., Branke J., Filipič B., 
    Smith J. (eds) Parallel Problem Solving from Nature – PPSN XIII. PPSN 2014. 
    Lecture Notes in Computer Science, vol 8672. Springer, Cham
    
    """
    
    def __init__(self, problem, population):
        ea.MoeaAlgorithm.__init__(self, problem, population) # 先调用父类构造方法
        if str(type(population)) != "<class 'Population.Population'>":
            raise RuntimeError('传入的种群对象必须为Population类型')
        self.name = 'NSGA3-DE'
        if self.problem.M < 10:
            self.ndSort = ea.ndsortESS # 采用ENS_SS进行非支配排序
        else:
            self.ndSort = ea.ndsortTNS # 高维目标采用T_ENS进行非支配排序，速度一般会比ENS_SS要快
        self.selFunc = 'tour' # 基向量选择方式，采用锦标赛选择
        if population.Encoding == 'RI':
            self.mutOper = ea.Mutde(F = 0.5) # 生成差分变异算子对象
            self.recOper = ea.Xovbd(XOVR = 0.5, Half = True) # 生成二项式分布交叉算子对象，这里的XOVR即为DE中的Cr
        else:
            raise RuntimeError('编码方式必须为''RI''.')
        self.F = 0.5 # 差分变异缩放因子（可以设置为一个数也可以设置为一个列数与种群规模数目相等的列向量）
        self.pc = 0.2 # 交叉概率
    
    def reinsertion(self, population, offspring, NUM, uniformPoint):
        
        """
        描述:
            重插入个体产生新一代种群（采用父子合并选择的策略）。
            NUM为所需要保留到下一代的个体数目。
            
        """
        
        # 父子两代合并
        population = population + offspring
        # 选择个体保留到下一代
        [levels, criLevel] = self.ndSort(self.problem.maxormins * population.ObjV, NUM, None, population.CV) # 对NUM个个体进行非支配分层
        chooseFlag = ea.refselect(self.problem.maxormins * population.ObjV, levels, criLevel, NUM, uniformPoint, True) # 根据参考点选择个体(True表示使用伪随机数方法，可以提高速度，详见refselect帮助文档)
        return population[chooseFlag]
    
    def run(self, prophetPop = None): # prophetPop为先知种群（即包含先验知识的种群）
        #==========================初始化配置===========================
        population = self.population
        self.initialization() # 初始化算法模板的一些动态参数
        #===========================准备进化============================
        uniformPoint, NIND = ea.crtup(self.problem.M, population.sizes) # 生成在单位目标维度上均匀分布的参考点集
        if population.Chrom is None or population.sizes != NIND: # 如果种群染色体还没初始化或者规模与NIND不一致，则进行初始化
            population.initChrom(NIND) # 初始化种群染色体矩阵（内含解码，详见Population类的源码），此时种群规模将调整为uniformPoint点集的大小，initChrom函数会把种群规模给重置
        else:
            population.Phen = population.decoding() # 染色体解码
        self.problem.aimFunc(population) # 计算种群的目标函数值
        self.evalsNum = population.sizes # 记录评价次数
        # 插入先验知识（注意：这里不会对先知种群prophetPop的合法性进行检查，故应确保prophetPop是一个种群类且拥有合法的Chrom、ObjV、Phen等属性）
        if prophetPop is not None:
            population = (prophetPop + population)[:NIND] # 插入先知种群
        #===========================开始进化============================
        while self.terminated(population) == False:
            # 进行差分进化操作
            r0 = ea.selecting(self.selFunc, population.FitnV, NIND) # 得到基向量索引
            offspring = population.copy() # 存储子代种群
            offspring.Chrom = self.mutOper.do(offspring.Encoding, offspring.Chrom, offspring.Field, [r0]) # 变异
            tempPop = population + offspring # 当代种群个体与变异个体进行合并（为的是后面用于重组）
            offspring.Chrom = self.recOper.do(tempPop.Chrom) # 重组
            # 求进化后个体的目标函数值
            offspring.Phen = offspring.decoding() # 染色体解码
            self.problem.aimFunc(offspring) # 计算目标函数值
            self.evalsNum += offspring.sizes # 更新评价次数
            # 重插入生成新一代种群
            population = self.reinsertion(population, offspring, NIND, uniformPoint)
            
        return self.finishing(population) # 调用finishing完成后续工作并返回结果
