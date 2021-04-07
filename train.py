from chainer import global_config
from chainer.iterators import SerialIterator
from stylegan.dataset import ImageDataset
from stylegan.networks import Generator, Discriminator
from stylegan.training import AdamTriple, CustomUpdater, CustomTrainer
#from stylegan.augumentation import AugmentationPipeline
from interface.args import CustomArgumentParser
from interface.argtypes import uint, natural, ufloat, positive, rate
from utilities.stdio import eprint
from utilities.filesys import mkdirs, build_filepath

def main(args):
	print("Initializing models...")
	generator = Generator(args.size, args.depth, args.levels, *args.channels, not args.narrow)
	averaged_generator = Generator(args.size, args.depth, args.levels, *args.channels, not args.narrow)
	discriminator = Discriminator(args.levels, args.channels[1], args.channels[0], args.group)
	generator.to_device(args.device)
	averaged_generator.to_device(args.device)
	discriminator.to_device(args.device)
	optimizers = AdamTriple(args.alphas, args.betas[0], args.betas[1])
	optimizers.setup(generator, discriminator)

	mkdirs(args.dest)
	dataset = ImageDataset(args.dataset, generator.resolution, args.preload)
	iterator = SerialIterator(dataset, args.batch, repeat=True, shuffle=True)
	updater = CustomUpdater(generator, averaged_generator, discriminator, iterator, optimizers, args.ema, args.lsgan)
	updater.enable_style_mixing(args.mix)
	updater.enable_r1_regularization(args.gamma)
	updater.enable_path_length_regularization()

	if args.snapshot is not None:
		updater.load_states(args.snapshot)
	trainer = CustomTrainer(updater, args.epoch, args.dest)
	trainer.hook_state_save(1000)
	trainer.hook_image_generation(1000, 32)
	trainer.enable_reports(500)
	trainer.enable_progress_bar(1)
	trainer.run()
	generator.save_weights(build_filepath(args.dest, "gen", "hdf5"))
	updater.save_states(build_filepath(args.dest, "all", "hdf5"))

def parse_args():
	parser = CustomArgumentParser("")
	parser.add_argument("dataset", metavar="DATASET_DIR", help="dataset directory which stores images")
	parser.add_argument("-p", "--preload", action="store_true", help="preload all dataset into RAM")

	parser.add_argument("-s", "--snapshot", metavar="FILE", help="snapshot")
	parser.add_argument("-g", "--group", type=natural, default=16, help="")

	parser.add_argument("-e", "--epoch", type=natural, default=1, help="")
	parser.add_argument("-r", "--gamma", "--l2-batch", dest="gamma", type=ufloat, default=10, help="")
	parser.add_argument("-L", "--lsgan", "--least-squares", action="store_true", help="")
	parser.add_argument("-i", "--mixing", metavar="RATE", dest="mix", type=rate, default=0.5, help="")

	parser.add_argument("-A", "--alphas", metavar="ALPHA", type=positive, nargs=3, default=(0.00002, 0.002, 0.002), help="Adam's coefficients of learning rates of mapper, generator, and discriminator")
	parser.add_argument("-B", "--betas", metavar="BETA", type=rate, nargs=2, default=(0.0, 0.99), help="Adam's exponential decay rates of the 1st and 2nd order moments")
	parser.add_argument("-u", "--print-interval", metavar="ITER", dest="print", type=uint, nargs=2, default=(5, 500), help="")
	parser.add_argument("-l", "--write-interval", metavar="ITER", dest="write", type=uint, nargs=4, default=(1000, 3000, 500, 500), help="")
	return parser.add_output_args(default_dest="results").add_model_args().add_evaluation_args().parse_args()

if __name__ == "__main__":
	global_config.train = True
	global_config.autotune = True
	global_config.cudnn_deterministic = False
	try:
		main(parse_args())
	except KeyboardInterrupt:
		eprint("KeyboardInterrupt")
		exit(1)
