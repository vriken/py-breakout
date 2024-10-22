import numpy as np
from scipy.stats import norm, linregress

def calculate_moving_average(data, window):
    return np.convolve(data, np.ones(window), 'valid') / window

def calculate_rsi(data, period):
    delta = np.diff(data)
    gain = (delta * 0).copy()
    loss = (delta * 0).copy()
    gain[delta > 0] = delta[delta > 0]
    loss[-delta > 0] = -delta[-delta > 0]
    avg_gain = np.convolve(gain, np.ones(period), 'valid') / period
    avg_loss = np.convolve(loss, np.ones(period), 'valid') / period
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_slope(data):
    x = np.arange(len(data))
    slope, _, _, _, _ = linregress(x, data)
    return slope


def objective_function(weights, expected_returns, cov_matrix, lambda_param=0.65):
    portfolio_return = np.sum(weights * expected_returns)
    portfolio_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    return lambda_param * portfolio_return - (1 - lambda_param) * portfolio_risk

class BlackWidowOptimization:
    def __init__(self, num_spiders, num_iterations, expected_returns, cov_matrix, num_assets):
        self.num_spiders = num_spiders
        self.num_iterations = num_iterations
        self.expected_returns = expected_returns
        self.cov_matrix = cov_matrix
        self.num_assets = num_assets
        self.best_solution = None
        self.best_fitness = float('-inf')

    def initialize_population(self):
        population = []
        for _ in range(self.num_spiders):
            weights = np.random.random(self.num_assets)
            weights /= np.sum(weights)
            population.append(weights)
        return population

    def fitness(self, weights):
        return objective_function(weights, self.expected_returns, self.cov_matrix)

    def procreate(self, male, female):
        child = (male + female) / 2
        child /= np.sum(child)
        return child

    def mutate(self, spider):
        mutation = np.random.normal(0, 0.1, self.num_assets)
        spider += mutation
        spider = np.clip(spider, 0, 1)
        spider /= np.sum(spider)
        return spider

    def optimize(self):
        population = self.initialize_population()

        for _ in range(self.num_iterations):
            # Evaluate fitness
            fitnesses = [self.fitness(spider) for spider in population]
            
            # Find best solution
            best_index = np.argmax(fitnesses)
            if fitnesses[best_index] > self.best_fitness:
                self.best_solution = population[best_index]
                self.best_fitness = fitnesses[best_index]

            # Procreation and cannibalism
            new_population = [self.best_solution]
            while len(new_population) < self.num_spiders:
                male, female = np.random.choice(population, 2, replace=False)
                child = self.procreate(male, female)
                if np.random.random() < 0.1:  # 10% chance of mutation
                    child = self.mutate(child)
                new_population.append(child)

            population = new_population

        return self.best_solution, self.best_fitness